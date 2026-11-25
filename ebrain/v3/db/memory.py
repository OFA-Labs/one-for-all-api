"""In-memory authoritative ledger reference implementation.

This backend exercises the complete admission/reservation/outbox/fence pipeline
under a real lock so concurrency properties are testable without Postgres. It is
a deterministic reference and is explicitly NOT proof of RLS or Postgres
isolation (see ``db/postgres.py`` and the gated integration tests).
"""
from __future__ import annotations

import threading
from typing import Mapping

from ..auth.context import authorize, check_read_epoch
from ..clocks import Clock, SystemClock
from ..config import V3Config
from ..contracts import (
    AUTHORITY_RANK,
    Action,
    AdmissionReceipt,
    AuthorizedContext,
    Claim,
    ClaimKind,
    Decision,
    DecisionState,
    FactKey,
    IdentityEvent,
    Limits,
    OutboxJob,
    PendingImpact,
    ReceiptStatus,
    Snapshot,
    SourceContract,
    SourceRevision,
    Span,
    UsageReservation,
    WriteRequest,
    digest_of,
)
from ..errors import (
    AmbiguousIdentity,
    Forbidden,
    IdempotencyConflict,
    StaleBase,
)
from ..ingest.gate import sanitize
from ..quotas.plans import PlanPolicy
from ..workers.outbox import Outbox


class MemoryLedger:
    """Ordered, append-only, tenant-scoped, atomic admission boundary."""

    def __init__(
        self,
        *,
        cfg: V3Config | None = None,
        clock: Clock | None = None,
        plan: PlanPolicy | None = None,
        org_id: str = "org-demo",
    ) -> None:
        self.cfg = (cfg or V3Config()).validate()
        self.clock = clock or SystemClock()
        self.plan = plan or PlanPolicy("individual_free")
        self.org_id = org_id
        self._lock = threading.RLock()
        self._seq = 0
        self._receipts: dict[tuple[str, str], AdmissionReceipt] = {}
        self._idem_keys: dict[tuple[str, str], str] = {}
        self._claims: list[Claim] = []
        self._claims_by_id: dict[str, Claim] = {}
        self._fact_heads: dict[str, tuple[str, int]] = {}
        self._identity_events: list[IdentityEvent] = []
        self._decisions: dict[str, Decision] = {}
        self._pending: dict[str, PendingImpact] = {}
        self._usage: dict[str, UsageReservation] = {}
        self._suppressed: set[str] = set()
        self._outbox = Outbox(self.cfg)
        self._observed: dict[str, int] = {}
        self._recorded: dict[str, str] = {}
        self._event_payloads: dict[int, dict[str, object]] = {}

    # -- helpers -------------------------------------------------------------

    def _usage_for(self, scope: str) -> UsageReservation:
        return self._usage.setdefault(
            scope, UsageReservation(scope=scope, plan_revision=self.plan.revision)
        )

    def _source(self, request: WriteRequest) -> SourceRevision:
        return SourceRevision(
            source_id=request.source_id or "client-declared",
            revision=request.source_revision or "1",
            digest=digest_of({
                "text": request.text,
                "value": request.value,
                "source_id": request.source_id,
                "revision": request.source_revision,
            }),
            parser_version="v3-1",
            contract=request.source_contract,
            spans=(),
        )

    # -- snapshot / reads ----------------------------------------------------

    def snapshot(self, ctx: AuthorizedContext) -> Snapshot:
        with self._lock:
            return Snapshot(
                org_id=self.org_id,
                knowledge_seq=self._seq,
                valid_at=self.clock.iso(),
                identity_generation=self.cfg.identity_generation,
                policy_version=self.cfg.policy_version,
                auth_epoch=ctx.auth_epoch,
                retrieval_generation=self.cfg.retrieval_generation,
                model_generation=self.cfg.model_manifest_id,
            )

    def load_slice(
        self, ctx: AuthorizedContext, keys: tuple[FactKey, ...], seq: int
    ) -> tuple[Claim, ...]:
        with self._lock:
            check_read_epoch(ctx, Snapshot(
                org_id=self.org_id, knowledge_seq=seq, valid_at="",
                auth_epoch=ctx.auth_epoch,
            ))
            wanted = {k.canonical() for k in keys}
            out: list[Claim] = []
            for claim in self._claims:
                if claim.knowledge_seq > seq:
                    continue
                if wanted and claim.key.canonical() not in wanted:
                    continue
                if claim.key.scope != ctx.scope:
                    continue
                if claim.fact_id in self._suppressed:
                    continue
                if ctx.allowed_predicates and "*" not in ctx.allowed_predicates \
                        and claim.key.predicate not in ctx.allowed_predicates:
                    continue
                out.append(claim)
            return tuple(out)

    def claim_by_id(self, claim_id: str) -> Claim | None:
        """O(1) accepted-claim lookup (no full-ledger scan per write)."""
        return self._claims_by_id.get(claim_id)

    def pending(self, ctx: AuthorizedContext, seq: int) -> tuple[PendingImpact, ...]:
        with self._lock:
            return tuple(
                p for p in self._pending.values()
                if (p.key is None or p.key.scope == ctx.scope)
                and p.created_seq <= seq
                and p.active
            )

    def identity_events(self, ctx: AuthorizedContext, seq: int) -> tuple[IdentityEvent, ...]:
        with self._lock:
            return tuple(
                e for e in self._identity_events
                if e.knowledge_seq <= seq and e.key.scope == ctx.scope
            )

    def decisions(self, ctx: AuthorizedContext, seq: int) -> tuple[Decision, ...]:
        with self._lock:
            return tuple(
                d for d in self._decisions.values()
                if d.applied_seq is None or d.applied_seq <= seq
            )

    # -- mutations -----------------------------------------------------------

    def _append_event(self, payload: Mapping[str, object]) -> int:
        self._seq += 1
        self._event_payloads[self._seq] = dict(payload)
        return self._seq

    def admit(self, ctx: AuthorizedContext, request: WriteRequest) -> AdmissionReceipt:
        """Atomic admission: authorize -> gate -> idempotency -> head -> quota -> commit."""
        if ctx.principal.org_id != self.org_id:
            raise Forbidden("organization mismatch")
        if request.key is not None and (
            request.key.scope != ctx.scope or request.key.org_id != ctx.principal.org_id
        ):
            raise Forbidden("key scope does not match authorized scope")
        predicate = request.key.predicate if request.key else "*"
        authorize(ctx, predicate=predicate, action=Action.WRITE, config=self.cfg,
                  now_iso=self.clock.iso())
        # Pre-persistence gate (mandatory, cannot be disabled).
        gate = sanitize(request.text or str(request.value or ""), self.cfg)
        request_digest = digest_of({
            "op_id": request.op_id,
            "payload": gate.digest,
            "kind": request.kind.value,
            "key": request.key.canonical() if request.key else "",
            "source": request.source_id,
            "revision": request.source_revision,
            "valid_from": request.valid_from,
            "valid_to": request.valid_to,
        })
        idem = (request.idempotency_key, request_digest)
        with self._lock:
            idem_scope_key = (ctx.scope, request.idempotency_key)
            prior_digest = self._idem_keys.get(idem_scope_key)
            if prior_digest is not None and prior_digest != request_digest:
                raise IdempotencyConflict("idempotency key reused with a different digest")
            existing = self._receipts.get(idem)
            if existing is not None:
                if existing.scope != ctx.scope or existing.auth_epoch != ctx.auth_epoch:
                    raise Forbidden("receipt belongs to a different authorized scope")
                return existing  # authorized idempotent replay

            key = request.key
            head = self._fact_heads.get(key.canonical()) if key else None
            if request.expected_head is not None and (
                head is None or head[0] != request.expected_head
            ):
                raise StaleBase("expected head does not match observed current head")

            ambiguous = key is None or bool(request.text) and key is None
            if key is not None and not key.resource_id:
                ambiguous = True
            noncurrent = request.source_contract in (
                SourceContract.EXTERNAL_OBSERVATION, SourceContract.DERIVED
            ) or request.kind in (ClaimKind.DERIVED, ClaimKind.EXTERNAL)

            usage = self._usage_for(ctx.scope)
            delta = UsageReservation(
                scope=ctx.scope,
                facts=0 if head else (0 if ambiguous else 1),
                events=1,
                bytes_=len(gate.sanitized.encode("utf-8")),
                jobs=1,
                pending=1 if ambiguous else 0,
                plan_revision=self.plan.revision,
            )
            self.plan.check(usage, delta, emergency=False)

            seq = self._append_event({
                "type": "admission", "scope": ctx.scope, "op_id": request.op_id,
                "digest": request_digest,
            })
            recorded_at = self.clock.iso()
            self._recorded[request.op_id] = recorded_at
            claim: Claim | None = None
            fact_id: str | None = None
            if key is not None and not noncurrent:
                fact_id = key.key_id
                # Authority is server-derived from grants at admission; lineage in
                # request text can never raise it.
                authority = "agent"
                for grant in ctx.principal.grants:
                    if grant.scope in ("*", ctx.scope) and (
                        not grant.predicates
                        or "*" in grant.predicates
                        or key.predicate in grant.predicates
                    ):
                        if AUTHORITY_RANK[grant.authority] > AUTHORITY_RANK[authority]:
                            authority = grant.authority
                claim = Claim(
                    claim_id="cl_" + digest_of({"op": request.op_id, "seq": seq})[:20],
                    key=key,
                    kind=request.kind if request.kind != ClaimKind.DERIVED else ClaimKind.ASSERTION,
                    value=(gate.sanitized if isinstance(request.value, str) else request.value)
                    if request.value is not None else gate.sanitized,
                    value_type=request.value_type,
                    unit=request.unit,
                    source=self._source(request),
                    principal_id=ctx.principal.subject,
                    grant_id=",".join(sorted(a.value for a in ctx.allowed_actions)),
                    authority=authority,  # type: ignore[arg-type]
                    policy_version=self.cfg.policy_version,
                    valid_from=request.valid_from or recorded_at,
                    valid_to=request.valid_to,
                    recorded_at=recorded_at,
                    knowledge_seq=seq,
                    base_seq=head[1] if head else 0,
                    observed_seq=request.observed_seq or seq,
                    digest=request_digest,
                    fact_id=fact_id,
                )
                self._claims.append(claim)
                self._claims_by_id[claim.claim_id] = claim
                self._fact_heads[key.canonical()] = (claim.claim_id, seq)

            if ambiguous:
                impact = PendingImpact(
                    impact_id="pi_" + digest_of({"op": request.op_id, "seq": seq})[:20],
                    scope=ctx.scope,
                    key=key,
                    domain=key.predicate if key else "unstructured",
                    reason="missing qualifiers or structured key",
                    created_seq=seq,
                    claim_id=claim.claim_id if claim else "",
                )
                self._pending[impact.impact_id] = impact

            job = OutboxJob(
                job_id=f"claim:{seq}",
                job_type="projection" if claim else "pending_review",
                scope=ctx.scope,
                payload_digest=request_digest,
                knowledge_seq=seq,
            )
            self._outbox.enqueue(job)
            self._outbox.mark_contiguous(seq)

            updated = UsageReservation(
                scope=ctx.scope,
                facts=usage.facts + delta.facts,
                events=usage.events + 1,
                bytes_=usage.bytes_ + delta.bytes_,
                jobs=usage.jobs + 1,
                pending=usage.pending + delta.pending,
                plan_revision=self.plan.revision,
            )
            self._usage[ctx.scope] = updated

            if ambiguous:
                status = ReceiptStatus.ACCEPTED_PENDING
            elif noncurrent:
                status = ReceiptStatus.ACCEPTED_NONCURRENT
            else:
                status = ReceiptStatus.APPLIED
            receipt = AdmissionReceipt(
                op_id=request.op_id,
                status=status,
                knowledge_seq=seq,
                request_digest=request_digest,
                scope=ctx.scope,
                auth_epoch=ctx.auth_epoch,
                reason=("pending" if ambiguous else "noncurrent evidence" if noncurrent else "applied"),
                fact_id=fact_id,
                claim_id=claim.claim_id if claim else None,
            )
            self._receipts[idem] = receipt
            self._idem_keys[idem_scope_key] = request_digest
            return receipt

    def record_identity_event(self, ctx: AuthorizedContext, event: IdentityEvent) -> int:
        authorize(ctx, predicate=event.key.predicate, action=Action.ADMIN)
        with self._lock:
            seq = self._append_event({"type": "identity", "event": event.event_id})
            stored = event.model_copy(update={"knowledge_seq": seq})
            self._identity_events.append(stored)
            self._outbox.enqueue(OutboxJob(
                job_id=f"identity:{seq}", job_type="projection", scope=ctx.scope,
                payload_digest=event.evidence_digest or digest_of({"event": event.event_id}),
                knowledge_seq=seq,
            ))
            self._outbox.mark_contiguous(seq)
            return seq

    def record_decision(self, ctx: AuthorizedContext, decision: Decision) -> Decision:
        action = Action.REVIEW if Action.REVIEW in ctx.allowed_actions else Action.ADMIN
        authorize(ctx, predicate="*", action=action)
        with self._lock:
            if decision.decision_id in self._decisions:
                raise IdempotencyConflict("decision already recorded")
            self._decisions[decision.decision_id] = decision
            return decision

    def apply_decision(self, ctx: AuthorizedContext, decision_id: str, seq: int) -> Decision:
        with self._lock:
            decision = self._decisions.get(decision_id)
            if decision is None:
                raise AmbiguousIdentity("unknown decision")
            authorized = decision.model_copy(update={
                "state": DecisionState.APPLIED,
                "applied_seq": seq,
            })
            self._decisions[decision_id] = authorized
            return authorized

    def suppress(self, ctx: AuthorizedContext, fact_id: str, reason: str) -> None:
        """Append-only suppression tombstone; never physically delete history."""
        authorize(ctx, predicate="*", action=Action.ADMIN)
        with self._lock:
            seq = self._append_event({"type": "suppression", "fact_id": fact_id})
            self._suppressed.add(fact_id)
            self._outbox.enqueue(OutboxJob(
                job_id=f"suppression:{seq}", job_type="invalidate", scope=ctx.scope,
                payload_digest=digest_of({"fact_id": fact_id, "reason": reason}),
                knowledge_seq=seq,
            ))
            self._outbox.mark_contiguous(seq)

    def is_suppressed(self, fact_id: str) -> bool:
        with self._lock:
            return fact_id in self._suppressed

    def reserve(self, ctx: AuthorizedContext, usage: UsageReservation) -> None:
        with self._lock:
            self.plan.check(self._usage_for(ctx.scope), usage)

    @property
    def outbox(self) -> Outbox:
        return self._outbox

    @property
    def seq(self) -> int:
        return self._seq

    def limits(self, ctx: AuthorizedContext) -> Limits:
        with self._lock:
            return self.plan.to_limits(ctx.scope, self._usage_for(ctx.scope))

    def event_at(self, seq: int) -> dict[str, object] | None:
        with self._lock:
            return self._event_payloads.get(seq)
