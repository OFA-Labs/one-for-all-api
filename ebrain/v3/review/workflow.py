"""Review workflow with separation of duties, digest/version CAS and atomic apply.

A proposal never becomes authoritative by arrival. Queue pressure never
auto-approves. Absent/duplicate/overdue stewards remain blocked (M03).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..auth.context import authorize
from ..contracts import (
    Action,
    AuthorizedContext,
    Decision,
    DecisionState,
    Vote,
    digest_of,
)
from ..errors import (
    Forbidden,
    IdempotencyConflict,
    SemanticReject,
    StaleReview,
    Unauthenticated,
)

HIGH_RISK_KINDS = frozenset({
    "merge", "split", "rekey", "correction", "promotion", "policy", "erasure", "rollback",
})

# Owner-approved D08 review SLAs (critical 4h, high 24h, medium 72h, low 7d).
SLA_HOURS: dict[str, int] = {"critical": 4, "high": 24, "medium": 72, "low": 168}


@dataclass
class ReviewService:
    decisions: dict[str, Decision] = field(default_factory=dict)
    votes: dict[tuple[str, str], Vote] = field(default_factory=dict)
    applied: set[str] = field(default_factory=set)
    # Narrow owner-approved exception for isolated local/synthetic work only.
    single_user_exception: str = ""
    exception_log: tuple[str, ...] = ()

    def enable_local_single_user_exception(
        self, *, reason: str, isolated_local: bool, synthetic: bool
    ) -> None:
        if not (isolated_local and synthetic):
            raise Forbidden("single-user exception requires isolated local synthetic context")
        self.single_user_exception = reason
        self.exception_log += (f"local_single_user_exception:{reason}",)

    def propose(self, ctx: AuthorizedContext, decision: Decision) -> Decision:
        authorize(ctx, predicate="*", action=Action.PROPOSE)
        if decision.decision_id in self.decisions:
            raise IdempotencyConflict("decision id already used")
        if decision.state is not DecisionState.DRAFT:
            raise SemanticReject("a new proposal must start as a draft")
        stored = decision.model_copy(update={
            "digest": decision.digest or digest_of(decision.model_dump()),
        })
        self.decisions[decision.decision_id] = stored
        return stored

    def submit(self, ctx: AuthorizedContext, decision_id: str) -> Decision:
        authorize(ctx, predicate="*", action=Action.PROPOSE)
        decision = self._get(decision_id)
        if decision.state is not DecisionState.DRAFT:
            raise StaleReview("only a draft can be submitted")
        updated = decision.model_copy(update={"state": DecisionState.SUBMITTED})
        self.decisions[decision_id] = updated
        return updated

    def vote(self, ctx: AuthorizedContext, vote: Vote) -> Vote:
        authorize(ctx, predicate="*", action=Action.REVIEW)
        decision = self._get(vote.decision_id)
        if decision.state not in (DecisionState.SUBMITTED, DecisionState.UNDER_REVIEW):
            raise StaleReview("decision is not open for review")
        if ctx.principal.subject == decision.proposer and vote.approve:
            raise Forbidden("proposer cannot approve their own high-risk decision")
        if vote.version != decision.version or vote.digest != decision.digest:
            raise StaleReview("vote targets a stale decision version or digest")
        if vote.voter != ctx.principal.subject:
            raise Forbidden("vote voter must match the authenticated principal")
        key = (vote.decision_id, ctx.principal.subject)
        if key in self.votes:
            raise IdempotencyConflict("reviewer already voted on this version")
        self.votes[key] = vote
        return vote

    def _get(self, decision_id: str) -> Decision:
        decision = self.decisions.get(decision_id)
        if decision is None:
            raise Unauthenticated("decision not found")  # indistinguishable denial
        return decision

    def decide(self, ctx: AuthorizedContext, decision_id: str, approve: bool) -> Decision:
        authorize(ctx, predicate="*", action=Action.REVIEW)
        decision = self._get(decision_id)
        if decision.state not in (DecisionState.SUBMITTED, DecisionState.UNDER_REVIEW):
            raise StaleReview("decision is not open for decision")
        if approve:
            if decision.kind in HIGH_RISK_KINDS and ctx.principal.subject == decision.proposer:
                if not self.single_user_exception:
                    raise Forbidden("proposer cannot self-approve a high-risk decision")
                self.exception_log += (f"self_approved:{decision.decision_id}:"
                                       f"{ctx.principal.subject}",)
            if (decision.kind in HIGH_RISK_KINDS
                    and ctx.principal.subject != decision.proposer
                    and not self._has_independent_approval(decision)):
                raise Forbidden("high-risk decision requires an independent approver")
            state = DecisionState.APPROVED
        else:
            state = DecisionState.REJECTED
        updated = decision.model_copy(update={"state": state, "reviewer": ctx.principal.subject})
        self.decisions[decision_id] = updated
        return updated

    def _has_independent_approval(self, decision: Decision) -> bool:
        approvals = [
            v for v in self.votes.values()
            if v.decision_id == decision.decision_id
            and v.approve
            and v.voter != decision.proposer
            and v.version == decision.version
            and v.digest == decision.digest
        ]
        return bool(approvals)

    def apply(self, ctx: AuthorizedContext, decision_id: str, *, seq: int,
              expected_state: DecisionState = DecisionState.APPROVED) -> Decision:
        """CAS: an approved decision applies at most once at one commit cut."""
        authorize(ctx, predicate="*", action=Action.ADMIN)
        decision = self._get(decision_id)
        if decision.state is not expected_state:
            raise StaleReview("decision is not approved")
        if decision_id in self.applied:
            raise IdempotencyConflict("decision already applied")
        if decision.expires_at and decision.expires_at <= "":
            raise StaleReview("decision expired")
        self.applied.add(decision_id)
        updated = decision.model_copy(update={
            "state": DecisionState.APPLIED, "applied_seq": seq,
        })
        self.decisions[decision_id] = updated
        return updated

    def expire_or_stale(self, decision_id: str, *, new_branch: bool = False) -> Decision:
        decision = self._get(decision_id)
        if decision.state in (DecisionState.APPLIED, DecisionState.REJECTED):
            return decision
        state = DecisionState.STALE if new_branch else DecisionState.EXPIRED
        updated = decision.model_copy(update={"state": state})
        self.decisions[decision_id] = updated
        return updated

    def compensating_rollback(
        self, ctx: AuthorizedContext, *, original: Decision, reason: str, seq: int
    ) -> Decision:
        """Append-only logical rollback: new id/code, keeps all intervening events."""
        digest = digest_of({"rollback_of": original.decision_id, "reason": reason})
        rollback = Decision(
            decision_id="rb_" + digest[:20],
            kind="rollback",
            state=DecisionState.APPROVED,
            version=1,
            digest=digest,
            scope=original.scope,
            targets=original.targets,
            evidence=(original.digest,),
            proposer=ctx.principal.subject,
            reviewer=ctx.principal.subject,
            reason=reason,
        )
        self.decisions[rollback.decision_id] = rollback
        return self.apply(ctx, rollback.decision_id, seq=seq)

    def blocked_queue(self, ctx: AuthorizedContext) -> tuple[Decision, ...]:
        """Absent steward/duplicate/overdue decisions escalate and stay blocked."""
        authorize(ctx, predicate="*", action=Action.REVIEW)
        return tuple(
            d for d in self.decisions.values()
            if d.state in (DecisionState.SUBMITTED, DecisionState.UNDER_REVIEW)
            and (d.reviewer is None or d.expires_at is not None)
        )

    def escalations(self, ctx: AuthorizedContext, *, now_hours: int = 0) -> tuple[str, ...]:
        """Report SLA breaches without approving, dismissing or mutating state."""
        authorize(ctx, predicate="*", action=Action.REVIEW)
        out: list[str] = []
        for decision in self.blocked_queue(ctx):
            limit = SLA_HOURS[decision.priority]
            if now_hours >= limit:
                target = decision.reviewer or "unassigned"
                out.append(
                    f"escalate:{decision.decision_id}:{decision.priority}:{target}"
                )
        return tuple(sorted(out))

    def allowed_single_user_exception(
        self, *, isolated_local: bool, synthetic: bool, high_risk: bool
    ) -> bool:
        """Narrow local/synthetic exception only; never for production or pilot."""
        return isolated_local and synthetic and not high_risk
