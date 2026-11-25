"""Isolated PostgreSQL ledger adapter (M8).

Uses psycopg 3 (optional dependency, NOT installed in the planning venv). The
DSN is supplied by the test/ops harness from an environment variable whose NAME
is documented here; its VALUE is never printed, logged or stored in fixtures.
This adapter is disabled by default and is not imported by the legacy service.

STATUS: code and SQL are written; real-Postgres/RLS/concurrency execution is
BLOCKED_ENVIRONMENT in this workspace (no running Postgres/Docker daemon).
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Final, Iterator

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
    FactKey,
    IdentityEvent,
    Limits,
    PendingImpact,
    ReceiptStatus,
    Snapshot,
    SourceContract,
    SourceRevision,
    UsageReservation,
    WriteRequest,
    digest_of,
)
from ..errors import IdempotencyConflict, StaleBase, Unavailable
from ..ingest.gate import sanitize
from ..quotas.plans import PlanPolicy

DSN_ENV_VAR: Final = "EBRAIN_V3_TEST_PG_DSN"
MIGRATION_ENV_VAR: Final = "EBRAIN_V3_MIGRATION_PG_DSN"


def psycopg_available() -> bool:
    try:
        import psycopg  # noqa: F401
        return True
    except ImportError:
        return False


def _fact_id(key: FactKey) -> str:
    return key.key_id


class PostgresLedger:
    """Transactional admission under an org commit-row lock with FORCE RLS."""

    def __init__(
        self,
        *,
        dsn: str,
        cfg: V3Config | None = None,
        clock: Clock | None = None,
        plan: PlanPolicy | None = None,
    ) -> None:
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise Unavailable(
                "psycopg 3 is not installed; real-Postgres checks are NOT_RUN"
            ) from exc
        self._psycopg = psycopg
        self._dsn = dsn
        self.cfg = (cfg or V3Config()).validate()
        self.clock = clock or SystemClock()
        self.plan = plan or PlanPolicy("individual_free")
        # One transaction-managed connection per ledger instance avoids paying
        # TCP/TLS/auth + connection setup on every admitted fact. RLS context is
        # still set transaction-locally on every operation via _set_org().
        self._conn = self._psycopg.connect(self._dsn)
        self._conn_lock = threading.RLock()

    @contextmanager
    def _connect(self) -> Iterator[Any]:
        """Yield the pooled connection inside a committed/rolled-back transaction."""
        with self._conn_lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def record_decision(self, ctx: AuthorizedContext, decision: Decision) -> Decision:
        """Persist an applied/reviewed decision as an authoritative control event."""
        action = Action.REVIEW if Action.REVIEW in ctx.allowed_actions else Action.ADMIN
        authorize(ctx, predicate="*", action=action)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "INSERT INTO v3_decision(org_id, decision_id, scope, kind, state, version, "
                    "digest, targets, evidence, preconditions, proposer, reviewer, reason, "
                    "expires_at, applied_seq, impact_digest) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::text[],%s::text[],%s::text[],%s,%s,%s,%s,%s,%s) "
                    "ON CONFLICT (org_id, decision_id) DO UPDATE SET "
                    "state=EXCLUDED.state, applied_seq=EXCLUDED.applied_seq",
                    (ctx.principal.org_id, decision.decision_id, decision.scope,
                     decision.kind, decision.state.value, decision.version, decision.digest,
                     list(decision.targets), list(decision.evidence),
                     list(decision.preconditions), decision.proposer, decision.reviewer,
                     decision.reason, decision.expires_at, decision.applied_seq,
                     decision.impact_digest),
                )
        return decision

    def suppress(self, ctx: AuthorizedContext, fact_id: str, reason: str) -> None:
        """Append-only suppression tombstone; never physically delete evidence."""
        authorize(ctx, predicate="*", action=Action.ADMIN)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute("SELECT knowledge_seq FROM v3_org_state WHERE org_id=%s FOR UPDATE",
                            (ctx.principal.org_id,))
                seq = int(cur.fetchone()[0]) + 1
                cur.execute(
                    "INSERT INTO v3_suppression(org_id, fact_id, seq, reason_code) "
                    "VALUES (%s,%s,%s,%s)",
                    (ctx.principal.org_id, fact_id, seq, reason),
                )
                cur.execute(
                    "UPDATE v3_claim SET suppressed=true WHERE org_id=%s AND fact_id=%s",
                    (ctx.principal.org_id, fact_id),
                )
                cur.execute(
                    "INSERT INTO v3_event(org_id, seq, event_id, scope, op_id, payload_digest, "
                    "event_type, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,'suppression',%s)",
                    (ctx.principal.org_id, seq, f"sup_{seq}", ctx.scope,
                     fact_id, digest_of({"fact_id": fact_id, "reason": reason}),
                     self.clock.iso()),
                )
                cur.execute(
                    "INSERT INTO v3_outbox(org_id, job_id, job_type, scope, payload_digest, seq, state) "
                    "VALUES (%s,%s,'invalidate',%s,%s,%s,'pending')",
                    (ctx.principal.org_id, f"suppression:{seq}", ctx.scope,
                     digest_of({"fact_id": fact_id, "reason": reason}), seq),
                )
                cur.execute("UPDATE v3_org_state SET knowledge_seq=%s WHERE org_id=%s",
                            (seq, ctx.principal.org_id))

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _set_org(cur: Any, org_id: str) -> None:
        cur.execute("SELECT set_config('v3.org_id', %s, true)", (org_id,))

    def snapshot(self, ctx: AuthorizedContext) -> Snapshot:
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT knowledge_seq, policy_version, identity_generation, auth_epoch "
                    "FROM v3_org_state WHERE org_id = %s FOR SHARE", (ctx.principal.org_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise Unavailable("organization state is missing")
                return Snapshot(
                    org_id=ctx.principal.org_id,
                    knowledge_seq=int(row[0]),
                    valid_at=self.clock.iso(),
                    policy_version=str(row[1]),
                    identity_generation=int(row[2]),
                    auth_epoch=int(row[3]),
                    retrieval_generation=self.cfg.retrieval_generation,
                    model_generation=self.cfg.model_manifest_id,
                )

    def admit(self, ctx: AuthorizedContext, request: WriteRequest) -> AdmissionReceipt:
        """One transaction: lock org row -> recheck grants -> reserve -> append."""
        predicate = request.key.predicate if request.key else "*"
        authorize(ctx, predicate=predicate, action=Action.WRITE, config=self.cfg,
                  now_iso=self.clock.iso())
        gate = sanitize(request.text or str(request.value or ""), self.cfg)
        request_digest = digest_of({
            "op": request.op_id, "payload": gate.digest, "kind": request.kind.value,
            "key": request.key.canonical() if request.key else "",
            "source": request.source_id, "revision": request.source_revision,
            "valid_from": request.valid_from, "valid_to": request.valid_to,
        })
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    self._set_org(cur, ctx.principal.org_id)
                    cur.execute(
                        "SELECT knowledge_seq FROM v3_org_state WHERE org_id = %s FOR UPDATE",
                        (ctx.principal.org_id,),
                    )
                    row = cur.fetchone()
                    if row is None:
                        raise Unavailable("organization state is missing")
                    seq = int(row[0]) + 1

                    cur.execute(
                        "SELECT op_id, status, knowledge_seq, request_digest, scope, auth_epoch, "
                        "reason, fact_id, claim_id FROM v3_receipt "
                        "WHERE org_id = %s AND scope = %s AND idem_key_raw = %s",
                        (ctx.principal.org_id, ctx.scope, request.idempotency_key),
                    )
                    prior = cur.fetchone()
                    if prior is not None:
                        if prior[3] != request_digest:
                            raise IdempotencyConflict("idempotency key reused with different digest")
                        return AdmissionReceipt(
                            op_id=str(prior[0]), status=ReceiptStatus(str(prior[1])),
                            knowledge_seq=int(prior[2]), request_digest=str(prior[3]),
                            scope=str(prior[4]), auth_epoch=int(prior[5]),
                            reason=str(prior[6]), fact_id=prior[7], claim_id=prior[8],
                        )

                    head_id: str | None = None
                    if request.key is not None:
                        cur.execute(
                            "SELECT claim_id FROM v3_claim WHERE org_id=%s AND scope=%s "
                            "AND fact_key=%s AND suppressed=false ORDER BY seq DESC LIMIT 1",
                            (ctx.principal.org_id, ctx.scope, request.key.canonical()),
                        )
                        head_row = cur.fetchone()
                        head_id = str(head_row[0]) if head_row else None
                    if request.expected_head is not None and request.expected_head != head_id:
                        raise StaleBase("expected head does not match observed current head")

                    ambiguous = request.key is None or not request.key.resource_id
                    noncurrent = (
                        request.source_contract in (
                            SourceContract.EXTERNAL_OBSERVATION, SourceContract.DERIVED
                        )
                        or request.kind in (ClaimKind.DERIVED, ClaimKind.EXTERNAL)
                    )
                    cur.execute(
                        "SELECT facts, events, bytes, jobs, pending FROM v3_usage "
                        "WHERE org_id=%s AND scope=%s FOR UPDATE",
                        (ctx.principal.org_id, ctx.scope),
                    )
                    usage_row = cur.fetchone() or (0, 0, 0, 0, 0)
                    delta_facts = 0 if (ambiguous or head_id) else 1
                    delta_bytes = len(gate.sanitized.encode("utf-8"))
                    delta_pending = 1 if ambiguous else 0
                    self.plan.check(
                        UsageReservation(
                            scope=ctx.scope, facts=int(usage_row[0]), events=int(usage_row[1]),
                            bytes_=int(usage_row[2]), jobs=int(usage_row[3]),
                            pending=int(usage_row[4]),
                        ),
                        UsageReservation(
                            scope=ctx.scope, facts=delta_facts, events=1,
                            bytes_=delta_bytes, jobs=1, pending=delta_pending,
                        ),
                    )

                    recorded_at = self.clock.iso()
                    cur.execute(
                        "INSERT INTO v3_event(org_id, seq, event_id, scope, op_id, payload_digest, "
                        "event_type, recorded_at) VALUES (%s,%s,%s,%s,%s,%s,'admission',%s)",
                        (ctx.principal.org_id, seq, f"ev_{seq}", ctx.scope,
                         request.op_id, request_digest, recorded_at),
                    )
                    fact_id: str | None = None
                    claim_id: str | None = None
                    if request.key is not None and not noncurrent:
                        fact_id = _fact_id(request.key)
                        claim_id = "cl_" + digest_of({"op": request.op_id, "seq": seq})[:20]
                        source = SourceRevision(
                            source_id=request.source_id or "client-declared",
                            revision=request.source_revision or "1",
                            digest=request_digest, parser_version="v3-1",
                            contract=request.source_contract,
                        )
                        cur.execute(
                            "INSERT INTO v3_claim(org_id, claim_id, seq, scope, fact_key, "
                            "org_scope_key, kind, value_json, value_type, unit, source_id, "
                            "source_revision, principal_id, authority, delegated_by, "
                            "policy_version, valid_from, valid_to, "
                            "recorded_at, base_seq, observed_seq, digest, fact_id) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                            (ctx.principal.org_id, claim_id, seq, ctx.scope,
                             request.key.canonical(), f"{ctx.principal.org_id}|{ctx.scope}",
                             request.kind.value,
                             __import__("json").dumps(
                                 request.value if request.value is not None else gate.sanitized
                             ),
                             request.value_type, request.unit, source.source_id, source.revision,
                             ctx.principal.subject,
                             max(
                                 (g.authority for g in ctx.principal.grants
                                  if g.scope in ("*", ctx.scope)
                                  and (not g.predicates or "*" in g.predicates
                                       or (request.key is not None
                                           and request.key.predicate in g.predicates))),
                                 key=lambda a: AUTHORITY_RANK[a], default="agent"
                             ), "", self.cfg.policy_version,
                             request.valid_from or recorded_at, request.valid_to, recorded_at,
                             0 if head_id is None else seq - 1,
                             request.observed_seq or seq, request_digest, fact_id),
                        )
                    if ambiguous:
                        cur.execute(
                            "INSERT INTO v3_pending_impact(org_id, impact_id, scope, fact_key, "
                            "domain, reason, created_seq, claim_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (ctx.principal.org_id, f"pi_{seq}", ctx.scope,
                             request.key.canonical() if request.key else None,
                             request.key.predicate if request.key else "unstructured",
                             "missing qualifiers or structured key", seq, claim_id or ""),
                        )
                    cur.execute(
                        "INSERT INTO v3_outbox(org_id, job_id, job_type, scope, payload_digest, seq, state) "
                        "VALUES (%s,%s,%s,%s,%s,%s,'pending')",
                        (ctx.principal.org_id, f"claim:{seq}",
                         "projection" if claim_id else "pending_review", ctx.scope,
                         request_digest, seq),
                    )
                    cur.execute(
                        "INSERT INTO v3_usage(org_id, scope, facts, events, bytes, jobs, pending, "
                        "plan_revision) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, scope) DO UPDATE SET "
                        "facts=v3_usage.facts+EXCLUDED.facts, events=v3_usage.events+EXCLUDED.events, "
                        "bytes=v3_usage.bytes+EXCLUDED.bytes, jobs=v3_usage.jobs+EXCLUDED.jobs, "
                        "pending=v3_usage.pending+EXCLUDED.pending",
                        (ctx.principal.org_id, ctx.scope, delta_facts, 1, delta_bytes, 1,
                         delta_pending, self.plan.revision),
                    )
                    cur.execute(
                        "UPDATE v3_org_state SET knowledge_seq=%s, updated_at=%s WHERE org_id=%s",
                        (seq, recorded_at, ctx.principal.org_id),
                    )
                    status = (
                        ReceiptStatus.ACCEPTED_PENDING if ambiguous
                        else ReceiptStatus.ACCEPTED_NONCURRENT if noncurrent
                        else ReceiptStatus.APPLIED
                    )
                    reason = ("pending" if ambiguous else
                              "noncurrent evidence" if noncurrent else "applied")
                    idem_key = digest_of({"key": request.idempotency_key, "digest": request_digest})
                    cur.execute(
                        "INSERT INTO v3_receipt(org_id, idem_key, idem_key_raw, op_id, status, "
                        "knowledge_seq, request_digest, scope, auth_epoch, reason, fact_id, claim_id) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
                        "ON CONFLICT (org_id, scope, idem_key_raw) DO NOTHING",
                        (ctx.principal.org_id, idem_key, request.idempotency_key,
                         request.op_id, status.value, seq, request_digest, ctx.scope,
                         ctx.auth_epoch, reason, fact_id, claim_id),
                    )
                    if cur.rowcount == 0:
                        raise IdempotencyConflict("idempotency key reused with different digest")
                    cur.execute(
                        "INSERT INTO v3_audit(org_id, seq, actor, action, digest) "
                        "VALUES (%s,%s,%s,'admit',%s)",
                        (ctx.principal.org_id, seq, ctx.principal.subject, request_digest),
                    )
                    return AdmissionReceipt(
                        op_id=request.op_id, status=status, knowledge_seq=seq,
                        request_digest=request_digest, scope=ctx.scope,
                        auth_epoch=ctx.auth_epoch, reason=reason,
                        fact_id=fact_id, claim_id=claim_id,
                    )
        except self._psycopg.errors.UniqueViolation as exc:
            raise IdempotencyConflict("scoped idempotency conflict") from exc

    def load_slice(
        self, ctx: AuthorizedContext, keys: tuple[FactKey, ...], seq: int
    ) -> tuple[Claim, ...]:
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                check_read_epoch(ctx, Snapshot(
                    org_id=ctx.principal.org_id, knowledge_seq=seq,
                    valid_at="", auth_epoch=ctx.auth_epoch,
                ))
                base = (
                    "SELECT claim_id, seq, scope, fact_key, kind, value_json, value_type, unit, "
                    "source_id, source_revision, principal_id, authority, policy_version, valid_from, "
                    "valid_to, recorded_at, base_seq, observed_seq, digest, fact_id "
                    "FROM v3_claim WHERE org_id=%s AND scope=%s AND seq<=%s AND suppressed=false "
                )
                params: list[object] = [ctx.principal.org_id, ctx.scope, seq]
                if keys:
                    base += "AND fact_key = ANY(%s) "
                    params.append([k.canonical() for k in keys])
                cur.execute(base + "ORDER BY seq", tuple(params))
                out: list[Claim] = []
                import json
                for r in cur.fetchall():
                    out.append(Claim(
                        claim_id=str(r[0]), knowledge_seq=int(r[1]),
                        key=FactKey.from_canonical(str(r[3])),
                        kind=ClaimKind(str(r[4])),
                        value=r[5],  # psycopg decodes jsonb to native Python values
                        value_type=str(r[6]), unit=r[7],
                        source=SourceRevision(
                            source_id=str(r[8]), revision=str(r[9]), digest=str(r[18]),
                            parser_version="v3-1",
                            contract=SourceContract.FIRST_PARTY_DECLARED,
                        ),
                        principal_id=str(r[10]), authority=r[11],
                        policy_version=str(r[12]),
                        valid_from=r[13].isoformat() if r[13] is not None else None,
                        valid_to=r[14].isoformat() if r[14] is not None else None,
                        recorded_at=r[15].isoformat() if hasattr(r[15], "isoformat") else str(r[15]),
                        base_seq=int(r[16]), observed_seq=int(r[17]), digest=str(r[18]),
                        fact_id=r[19],
                    ))
                return tuple(out)

    def query_bundle(self, ctx: AuthorizedContext, keys: tuple[FactKey, ...]) -> dict[str, object]:
        """Snapshot + eligible claims + control-set counts in ONE DB round trip.

        The common case has no identity/decision/pending/control rows, so the
        authoritative query needs only one connection instead of five. If any
        control set is non-empty the caller loads it through the normal methods.
        """
        from ..clocks import SystemClock
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT knowledge_seq, policy_version, identity_generation, auth_epoch "
                    "FROM v3_org_state WHERE org_id=%s FOR SHARE", (ctx.principal.org_id,)
                )
                row = cur.fetchone()
                if row is None:
                    raise Unavailable("organization state is missing")
                seq = int(row[0])
                snapshot = Snapshot(
                    org_id=ctx.principal.org_id, knowledge_seq=seq,
                    valid_at=SystemClock().iso(), policy_version=str(row[1]),
                    identity_generation=int(row[2]), auth_epoch=int(row[3]),
                    retrieval_generation=self.cfg.retrieval_generation,
                    model_generation=self.cfg.model_manifest_id,
                )
                base = (
                    "SELECT claim_id, seq, scope, fact_key, kind, value_json, value_type, unit, "
                    "source_id, source_revision, principal_id, authority, policy_version, "
                    "valid_from, valid_to, recorded_at, base_seq, observed_seq, digest, fact_id "
                    "FROM v3_claim WHERE org_id=%s AND scope=%s AND seq<=%s AND suppressed=false "
                )
                params: list[object] = [ctx.principal.org_id, ctx.scope, seq]
                if keys:
                    base += "AND fact_key = ANY(%s) "
                    params.append([k.canonical() for k in keys])
                cur.execute(base + "ORDER BY seq", tuple(params))
                claims: list[Claim] = []
                for r in cur.fetchall():
                    claims.append(Claim(
                        claim_id=str(r[0]), knowledge_seq=int(r[1]),
                        key=FactKey.from_canonical(str(r[3])), kind=ClaimKind(str(r[4])),
                        value=r[5], value_type=str(r[6]), unit=r[7],
                        source=SourceRevision(
                            source_id=str(r[8]), revision=str(r[9]), digest=str(r[18]),
                            parser_version="v3-1",
                            contract=SourceContract.FIRST_PARTY_DECLARED,
                        ),
                        principal_id=str(r[10]), authority=r[11], policy_version=str(r[12]),
                        valid_from=r[13].isoformat() if r[13] is not None else None,
                        valid_to=r[14].isoformat() if r[14] is not None else None,
                        recorded_at=r[15].isoformat() if hasattr(r[15], "isoformat") else str(r[15]),
                        base_seq=int(r[16]), observed_seq=int(r[17]), digest=str(r[18]),
                        fact_id=r[19],
                    ))
                cur.execute(
                    "SELECT (SELECT count(*) FROM v3_identity_event WHERE org_id=%s AND scope=%s AND seq<=%s), "
                    "(SELECT count(*) FROM v3_decision WHERE org_id=%s AND scope=%s), "
                    "(SELECT count(*) FROM v3_pending_impact WHERE org_id=%s AND scope=%s AND resolved_seq IS NULL), "
                    "(SELECT count(*) FROM v3_suppression)",
                    (ctx.principal.org_id, ctx.scope, seq,
                     ctx.principal.org_id, ctx.scope,
                     ctx.principal.org_id, ctx.scope),
                )
                counts = cur.fetchone()
                return {
                    "snapshot": snapshot, "claims": tuple(claims), "seq": seq,
                    "has_controls": any(int(c) > 0 for c in counts),
                }

    def identity_events(self, ctx: AuthorizedContext, seq: int) -> tuple[IdentityEvent, ...]:
        from ..contracts import FactKey, IdentityEventKind
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT event_id, kind, fact_key, fact_id, claim_id, actor, approval_id, "
                    "evidence_digest, generation, prior_event_id, reason FROM v3_identity_event "
                    "WHERE org_id=%s AND scope=%s AND seq<=%s ORDER BY seq",
                    (ctx.principal.org_id, ctx.scope, seq),
                )
                return tuple(
                    IdentityEvent(
                        event_id=str(r[0]), kind=IdentityEventKind(str(r[1])),
                        key=FactKey.from_canonical(str(r[2])), fact_id=r[3], claim_id=r[4],
                        actor=str(r[5]), approval_id=r[6], evidence_digest=str(r[7] or ""),
                        generation=int(r[8]), prior_event_id=r[9], reason=str(r[10] or ""),
                        knowledge_seq=seq,
                    ) for r in cur.fetchall()
                )

    def decisions(self, ctx: AuthorizedContext, seq: int) -> tuple[Decision, ...]:
        from ..contracts import DecisionState
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT decision_id, kind, state, version, digest, scope, targets, evidence, "
                    "preconditions, proposer, reviewer, reason, expires_at, applied_seq, "
                    "impact_digest FROM v3_decision WHERE org_id=%s AND scope=%s "
                    "AND (applied_seq IS NULL OR applied_seq<=%s)",
                    (ctx.principal.org_id, ctx.scope, seq),
                )
                return tuple(
                    Decision(
                        decision_id=str(r[0]), kind=str(r[1]), state=DecisionState(str(r[2])),
                        version=int(r[3]), digest=str(r[4]), scope=str(r[5]),
                        targets=tuple(r[6] or ()), evidence=tuple(r[7] or ()),
                        preconditions=tuple(r[8] or ()), proposer=str(r[9]), reviewer=r[10],
                        reason=str(r[11] or ""), expires_at=r[12], applied_seq=r[13],
                        impact_digest=str(r[14] or ""),
                    ) for r in cur.fetchall()
                )

    def pending(self, ctx: AuthorizedContext, seq: int) -> tuple[PendingImpact, ...]:
        from ..contracts import FactKey
        authorize(ctx, predicate="*", action=Action.QUERY)
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT impact_id, scope, fact_key, domain, reason, created_seq, "
                    "resolved_seq, claim_id FROM v3_pending_impact "
                    "WHERE org_id=%s AND scope=%s AND created_seq<=%s AND resolved_seq IS NULL",
                    (ctx.principal.org_id, ctx.scope, seq),
                )
                return tuple(
                    PendingImpact(
                        impact_id=str(r[0]), scope=str(r[1]),
                        key=FactKey.from_canonical(str(r[2])) if r[2] else None,
                        domain=str(r[3] or ""), reason=str(r[4]), created_seq=int(r[5]),
                        resolved_seq=r[6], claim_id=str(r[7] or ""),
                    ) for r in cur.fetchall()
                )

    def suppressed_ids(self, org_id: str) -> frozenset[str]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('v3.org_id', %s, true)", (org_id,))
                cur.execute("SELECT fact_id FROM v3_suppression WHERE org_id=%s", (org_id,))
                return frozenset(str(r[0]) for r in cur.fetchall())

    def limits(self, ctx: AuthorizedContext) -> Limits:
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute("SELECT facts, events, bytes, jobs, pending FROM v3_usage "
                            "WHERE org_id=%s AND scope=%s", (ctx.principal.org_id, ctx.scope))
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                return self.plan.to_limits(ctx.scope, UsageReservation(
                    scope=ctx.scope, facts=int(row[0]), events=int(row[1]),
                    bytes_=int(row[2]), jobs=int(row[3]), pending=int(row[4]),
                ))

    def reserve(self, ctx: AuthorizedContext, usage: UsageReservation) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                self._set_org(cur, ctx.principal.org_id)
                cur.execute(
                    "SELECT facts, events, bytes, jobs, pending FROM v3_usage "
                    "WHERE org_id=%s AND scope=%s FOR UPDATE",
                    (ctx.principal.org_id, ctx.scope),
                )
                row = cur.fetchone() or (0, 0, 0, 0, 0)
                self.plan.check(
                    UsageReservation(scope=ctx.scope, facts=int(row[0]), events=int(row[1]),
                                     bytes_=int(row[2]), jobs=int(row[3]), pending=int(row[4])),
                    usage,
                )
