"""Thin shared service façade used by HTTP, CLI, voice and MCP adapters.

All adapters delegate here; none implements authority, grants or current state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .auth.context import authorize
from .config import V3Config
from .contracts import (
    Action,
    AdmissionReceipt,
    Answer,
    AuthorizedContext,
    Claim,
    ClaimKind,
    Decision,
    FactKey,
    Limits,
    Selector,
    Vote,
    WriteRequest,
)
from .db.memory import MemoryLedger
from .identity.filing import FilingService
from .identity.ledger import IdentityLedger
from .quotas.plans import PlanPolicy
from .resolver.policy import DEFAULT_POLICY, PolicyVersion
from .retrieval.query import QueryService
from .review.workflow import ReviewService
from .sources.snapshots import SourceRegistry


@dataclass
class V3Service:
    ledger: MemoryLedger
    cfg: V3Config
    policy: PolicyVersion
    plan: PlanPolicy
    identity: IdentityLedger
    sources: SourceRegistry
    review: ReviewService
    filing: FilingService
    retriever: QueryService
    # Scoped (scope, predicate, resource) candidate index. Disposable accelerator:
    # the ledger remains authoritative and the index can be rebuilt at any time.
    _claim_index: dict[tuple[str, str, str], list[Claim]] = field(default_factory=dict)

    @classmethod
    def build(cls, *, cfg: V3Config | None = None, policy: PolicyVersion | None = None,
              plan: PlanPolicy | None = None, clock=None, ledger: MemoryLedger | None = None) -> V3Service:
        from .clocks import SystemClock
        cfg = (cfg or V3Config()).validate()
        policy = policy or DEFAULT_POLICY
        plan = plan or PlanPolicy("individual_free")
        ledger = ledger or MemoryLedger(cfg=cfg, clock=clock or SystemClock(), plan=plan)
        identity = IdentityLedger()
        review = ReviewService()
        return cls(
            ledger=ledger, cfg=cfg, policy=policy, plan=plan, identity=identity,
            sources=SourceRegistry(), review=review,
            filing=FilingService(identity, cfg),
            retriever=QueryService(cfg, policy),
        )

    def write(self, ctx: AuthorizedContext, request: WriteRequest) -> AdmissionReceipt:
        receipt = self.ledger.admit(ctx, request)
        if (isinstance(self.ledger, MemoryLedger) and request.key is not None
                and receipt.claim_id):
            claim = self.ledger.claim_by_id(receipt.claim_id)
            if claim is not None:
                self._claim_index.setdefault(
                    (ctx.scope, request.key.predicate, request.key.resource_id), []
                ).append(claim)
        return receipt

    def query(self, ctx: AuthorizedContext, selector: Selector) -> Answer:
        keys: tuple[FactKey, ...] = ()
        if (selector.resource_id and selector.predicate and selector.qualifiers
                and selector.scope == ctx.scope):
            keys = tuple(
                FactKey(
                    org_id=ctx.principal.org_id, scope=ctx.scope,
                    resource_namespace=selector.resource_namespace or "repo",
                    resource_id=selector.resource_id, predicate=selector.predicate,
                    kind=kind, qualifiers=selector.qualifiers,
                )
                for kind in (ClaimKind.ASSERTION, ClaimKind.OBSERVATION)
            )
        if hasattr(self.ledger, "query_bundle"):
            # Postgres: one connection for snapshot, exact claims and control counts.
            bundle = self.ledger.query_bundle(ctx, keys)
            snapshot = bundle["snapshot"]  # type: ignore[assignment]
            claims = bundle["claims"]      # type: ignore[assignment]
            seq = int(bundle["seq"])       # type: ignore[arg-type]
            if bundle["has_controls"]:
                identity = self.ledger.identity_events(ctx, seq)
                decisions = tuple(
                    d for d in self.review.decisions.values() if d.scope == ctx.scope
                ) + self.ledger.decisions(ctx, seq)
                pending = self.ledger.pending(ctx, seq)
                # Postgres query_bundle already filters suppressed=true claims.
                suppressed = frozenset()
            else:
                identity, decisions, pending, suppressed = (), (), (), frozenset()
        else:
            snapshot = self.ledger.snapshot(ctx)
            indexed = self._claim_index.get(
                (ctx.scope, selector.predicate, selector.resource_id)
            )
            if indexed is not None:
                claims = tuple(indexed)
            else:
                claims = self.ledger.load_slice(ctx, keys, snapshot.knowledge_seq)
            identity = self.ledger.identity_events(ctx, snapshot.knowledge_seq)
            # Reviewed decisions are authoritative control inputs. Merge the
            # in-process review ledger with ledger-recorded decisions.
            decisions = tuple(
                d for d in self.review.decisions.values() if d.scope == ctx.scope
            ) + self.ledger.decisions(ctx, snapshot.knowledge_seq)
            pending = self.ledger.pending(ctx, snapshot.knowledge_seq)
            suppressed = frozenset(self.ledger._suppressed)
        return self.retriever.answer(
            ctx, selector, snapshot, claims, identity, decisions, pending,
            suppressed=suppressed,
        )

    def propose(self, ctx: AuthorizedContext, decision: Decision) -> Decision:
        return self.review.propose(ctx, decision)

    def submit(self, ctx: AuthorizedContext, decision_id: str) -> Decision:
        return self.review.submit(ctx, decision_id)

    def vote(self, ctx: AuthorizedContext, vote: Vote) -> Vote:
        return self.review.vote(ctx, vote)

    def decide(self, ctx: AuthorizedContext, decision_id: str, approve: bool) -> Decision:
        return self.review.decide(ctx, decision_id, approve)

    def apply(self, ctx: AuthorizedContext, decision_id: str) -> Decision:
        snapshot = self.ledger.snapshot(ctx)
        applied = self.review.apply(ctx, decision_id, seq=snapshot.knowledge_seq + 1)
        # Persist the authoritative control event as well as the in-process record.
        self.ledger.record_decision(ctx, applied)
        return applied

    def limits(self, ctx: AuthorizedContext) -> Limits:
        authorize(ctx, predicate="*", action=Action.QUERY)
        return self.ledger.limits(ctx)
