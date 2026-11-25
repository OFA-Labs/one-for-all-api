"""Frozen, strict schema-3 domain contracts.

These models are the single executable source of truth for the V3 wire and
service contracts described in ``docs/ebrain/implementation-plan/CONTRACTS.md``.
They are deliberately independent of the legacy ``ebrain.models`` (schema 1).
No side effects at import time.

Invariants enforced here where possible (the rest are enforced by services):
  * canonical fact identity is org + scope + resource + predicate + kind + required qualifiers
  * a scalar current value exists only for ``current``; conflict/pending/withdrawn have none
  * a source proves an assertion was made, never that it is true
  * snapshots carry all versions needed to replay a historical cut
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base with no silently dropped/unknown fields (fail closed)."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class SchemaVersion(int, Enum):
    V1 = 1
    V3 = 3


class ClaimKind(str, Enum):
    ASSERTION = "assertion"      # intended decision / declared state
    OBSERVATION = "observation"  # observed runtime state
    DECISION = "decision"        # reviewed control/decision event
    DERIVED = "derived"          # derived artifact; never primary evidence
    EXTERNAL = "external"        # external evidence; never establishes current
    CONTROL = "control"          # tombstone / lifecycle / fence control event


class SourceContract(str, Enum):
    FIRST_PARTY_DECLARED = "first_party_declared"
    APPROVED_ARTIFACT = "approved_artifact"
    EXTERNAL_OBSERVATION = "external_observation"
    DERIVED = "derived"


AUTHORITY_RANK: Final[dict[str, int]] = {"agent": 0, "verified": 1, "human": 2}


class FactState(str, Enum):
    ABSENT = "absent"
    CURRENT = "current"
    CONFLICT = "conflict"
    WITHDRAWN = "withdrawn"
    PENDING_VERIFICATION = "pending_verification"
    UNKNOWN = "unknown"


class AnswerStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    AMBIGUOUS = "ambiguous"
    PENDING = "pending"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class ReceiptStatus(str, Enum):
    APPLIED = "applied"
    ACCEPTED_PENDING = "accepted_pending"
    ACCEPTED_NONCURRENT = "accepted_noncurrent"
    CONFLICT = "conflict"
    REJECTED = "rejected"


class DecisionState(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    STALE = "stale"
    APPLIED = "applied"
    FAILED = "failed"


class Action(str, Enum):
    WRITE = "write"
    QUERY = "query"
    EVIDENCE = "evidence"
    PROPOSE = "propose"
    REVIEW = "review"
    ADMIN = "admin"
    EXPORT = "export"


def digest_of(payload: Any) -> str:
    """Canonical SHA256 of any JSON-serializable payload (stable key order)."""
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------


class Grant(StrictModel):
    scope: str
    predicates: tuple[str, ...] = ()
    actions: tuple[Action, ...] = ()
    authority: Literal["human", "verified", "agent"] = "agent"
    expires_at: str | None = None  # ISO-8601 UTC; None = session-bounded
    can_delegate: bool = False


class Principal(StrictModel):
    subject: str
    org_id: str
    grants: tuple[Grant, ...] = ()
    auth_epoch: int = 0
    issuer: str | None = None
    audience: str | None = None
    credential_id: str = ""


class AuthorizedContext(StrictModel):
    """Server-derived; request bodies can never supply org/grants/authority."""

    principal: Principal
    request_id: str
    scope: str
    allowed_predicates: tuple[str, ...]
    allowed_actions: tuple[Action, ...]
    source_contract: SourceContract
    auth_epoch: int
    source_id: str = ""

    @model_validator(mode="after")
    def _nonempty_scope(self) -> AuthorizedContext:
        if not self.scope or not self.request_id:
            raise ValueError("scope and request_id are required")
        return self

    def allows(self, predicate: str, action: Action) -> bool:
        return (
            (
                not self.allowed_predicates
                or predicate == "*"
                or "*" in self.allowed_predicates
                or predicate in self.allowed_predicates
            )
            and action in self.allowed_actions
        )


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class FactKey(StrictModel):
    org_id: str
    scope: str
    resource_namespace: str
    resource_id: str
    predicate: str
    kind: ClaimKind
    qualifiers: tuple[tuple[str, str], ...] = ()

    def canonical(self) -> str:
        q = "&".join(f"{k}={v}" for k, v in sorted(self.qualifiers))
        parts = (
            self.org_id,
            self.scope,
            self.resource_namespace,
            self.resource_id,
            self.predicate,
            self.kind.value,
            q,
        )
        return "|".join(parts)

    @property
    def key_id(self) -> str:
        return "fk_" + digest_of({"key": self.canonical()})[:24]

    @staticmethod
    def from_canonical(value: str) -> FactKey:
        """Inverse of ``canonical()`` for persisted exact keys."""
        parts = value.split("|")
        if len(parts) != 7:
            raise ValueError("malformed canonical fact key")
        qualifiers = tuple(
            tuple(p.split("=", 1)) for p in parts[6].split("&") if "=" in p
        )  # type: ignore[arg-type]
        return FactKey(
            org_id=parts[0], scope=parts[1], resource_namespace=parts[2],
            resource_id=parts[3], predicate=parts[4], kind=ClaimKind(parts[5]),
            qualifiers=qualifiers,
        )


class IdentityEventKind(str, Enum):
    REGISTER = "register"
    BIND = "bind"
    UNBIND_CORRECTION = "unbind_correction"
    ALIAS = "alias"
    RETIRE_ALIAS = "retire_alias"
    MERGE = "merge"
    SPLIT = "split"
    REKEY = "rekey"


class IdentityEvent(StrictModel):
    event_id: str
    kind: IdentityEventKind
    key: FactKey
    fact_id: str | None = None
    claim_id: str | None = None
    actor: str
    approval_id: str | None = None
    evidence_digest: str = ""
    generation: int = 1
    knowledge_seq: int = 0
    prior_event_id: str | None = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Sources and claims
# ---------------------------------------------------------------------------


class Span(StrictModel):
    """Sanitized offsets into an immutable source revision, never raw prose."""

    start: int
    end: int
    digest: str
    label: str = ""


class SourceRevision(StrictModel):
    source_id: str
    revision: str
    digest: str
    parser_version: str
    contract: SourceContract
    spans: tuple[Span, ...] = ()
    acl_lineage: tuple[str, ...] = ()
    retracted: bool = False
    partial_scan: bool = False


class Claim(StrictModel):
    """A normalized, typed assertion with its provenance and time contract."""

    claim_id: str
    key: FactKey
    kind: ClaimKind
    value: Any = None
    value_type: str = "scalar"
    unit: str | None = None
    source: SourceRevision
    principal_id: str
    grant_id: str = ""
    authority: Literal["human", "verified", "agent"] = "agent"
    delegated_by: str = ""
    policy_version: str = "1"
    valid_from: str | None = None     # half-open UTC ISO-8601; None = unknown
    valid_to: str | None = None
    recorded_at: str = ""             # server assigned
    knowledge_seq: int = 0            # server commit cut
    base_seq: int = 0                 # observed base at admission
    observed_seq: int = 0             # newest cut observed by writer
    digest: str = ""
    fact_id: str | None = None
    equivalent_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _valid_interval(self) -> Claim:
        if self.valid_from and self.valid_to and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be greater than valid_from (half-open)")
        return self

    @property
    def is_current_eligible(self) -> bool:
        return (
            self.kind in (ClaimKind.ASSERTION, ClaimKind.OBSERVATION, ClaimKind.DECISION)
            and self.source.contract in (
                SourceContract.FIRST_PARTY_DECLARED,
                SourceContract.APPROVED_ARTIFACT,
            )
            and not self.source.retracted
            and not self.source.partial_scan
        )


# ---------------------------------------------------------------------------
# Snapshot, admission, fences, receipts
# ---------------------------------------------------------------------------


class Snapshot(StrictModel):
    org_id: str
    knowledge_seq: int
    valid_at: str
    identity_generation: int = 1
    policy_version: str = "1"
    auth_epoch: int = 0
    retrieval_generation: str = ""
    model_generation: str = ""


class PendingImpact(StrictModel):
    """Eligible incoming claim fences a possible current until reviewed."""

    impact_id: str
    scope: str
    key: FactKey | None = None
    domain: str = ""
    reason: str
    created_seq: int
    resolved_seq: int | None = None
    claim_id: str = ""

    @property
    def active(self) -> bool:
        return self.resolved_seq is None


class AdmissionReceipt(StrictModel):
    op_id: str
    status: ReceiptStatus
    knowledge_seq: int
    request_digest: str
    scope: str
    auth_epoch: int
    reason: str = ""
    fact_id: str | None = None
    claim_id: str | None = None
    processing_url: str = ""


class UsageReservation(StrictModel):
    scope: str
    facts: int = 0
    events: int = 0
    bytes_: int = Field(default=0, alias="bytes")
    jobs: int = 0
    pending: int = 0
    plan_revision: str = ""


class OutboxJob(StrictModel):
    job_id: str
    job_type: str
    scope: str
    payload_digest: str
    knowledge_seq: int
    attempts: int = 0
    lease_owner: str = ""
    lease_expires_seq: int = 0
    state: Literal["pending", "leased", "applied", "dead"] = "pending"
    last_error: str = ""


# ---------------------------------------------------------------------------
# Decisions / review
# ---------------------------------------------------------------------------


class Decision(StrictModel):
    decision_id: str
    kind: str                       # merge/split/retire/correction/rollback/promotion/policy
    state: DecisionState
    version: int
    digest: str
    scope: str
    targets: tuple[str, ...]
    evidence: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    proposer: str
    reviewer: str | None = None
    reason: str = ""
    priority: Literal["critical", "high", "medium", "low"] = "medium"
    expires_at: str | None = None
    applied_seq: int | None = None
    impact_digest: str = ""


class Vote(StrictModel):
    decision_id: str
    version: int
    voter: str
    approve: bool
    digest: str
    reason: str = ""


# ---------------------------------------------------------------------------
# Retrieval / answers
# ---------------------------------------------------------------------------


class Selector(StrictModel):
    """Structured selector. Missing qualifiers mean ambiguity, not a default."""

    scope: str
    resource_namespace: str = ""
    resource_id: str = ""
    predicate: str = ""
    kind: ClaimKind | None = None
    qualifiers: tuple[tuple[str, str], ...] = ()
    text: str = ""
    fact_id: str = ""


class Candidate(StrictModel):
    fact_id: str
    key: FactKey
    arm: str
    rank: int = 0
    score: float = 0.0
    protected: bool = False
    knowledge_seq: int = 0
    provenance_digest: str = ""


class CandidateSet(StrictModel):
    candidates: tuple[Candidate, ...] = ()
    coverage_seq: int = 0
    complete: bool = True
    arms: tuple[str, ...] = ()
    degradation: tuple[str, ...] = ()


class Provenance(StrictModel):
    source_id: str
    revision: str
    digest: str
    span: Span | None = None
    freshness: str = "unknown"       # fresh | stale | expired | unknown
    contract: SourceContract = SourceContract.FIRST_PARTY_DECLARED


class AnswerItem(StrictModel):
    fact_id: str
    key: FactKey
    state: FactState
    current_value: Any = None
    value_type: str = "scalar"
    confidence: float = 0.0
    provenance: tuple[Provenance, ...] = ()
    annotations: tuple[str, ...] = ()
    freshness: str = "unknown"

    @model_validator(mode="after")
    def _no_current_without_value(self) -> AnswerItem:
        if self.state is not FactState.CURRENT and self.current_value is not None:
            raise ValueError("only a current fact may carry a scalar current value")
        if self.state is FactState.CURRENT and self.current_value is None:
            raise ValueError("a current fact must carry a scalar current value")
        return self


class Answer(StrictModel):
    answer_status: AnswerStatus
    items: tuple[AnswerItem, ...] = ()
    snapshot: Snapshot
    degradation: tuple[str, ...] = ()
    completeness: tuple[str, ...] = ()
    receipts: tuple[AdmissionReceipt, ...] = ()
    cursor: str = ""
    request_id: str = ""

    @model_validator(mode="after")
    def _status_consistency(self) -> Answer:
        if self.answer_status is AnswerStatus.COMPLETE and any(
            i.state in (FactState.CONFLICT, FactState.PENDING_VERIFICATION, FactState.UNKNOWN)
            for i in self.items
        ):
            raise ValueError("complete answer cannot contain unresolved state as current")
        return self


# ---------------------------------------------------------------------------
# Service protocols (interfaces only; implementations live in milestone modules)
# ---------------------------------------------------------------------------


@runtime_checkable
class LedgerProtocol(Protocol):
    def admit(self, ctx: AuthorizedContext, request: "WriteRequest") -> AdmissionReceipt: ...

    def snapshot(self, ctx: AuthorizedContext) -> Snapshot: ...

    def load_slice(self, ctx: AuthorizedContext, keys: tuple[FactKey, ...], seq: int) -> tuple[Claim, ...]: ...

    def reserve(self, ctx: AuthorizedContext, usage: UsageReservation) -> None: ...


@runtime_checkable
class ResolverProtocol(Protocol):
    def resolve(
        self,
        claims: tuple[Claim, ...],
        events: tuple[IdentityEvent, ...],
        decisions: tuple[Decision, ...],
        pending: tuple[PendingImpact, ...],
        snapshot: Snapshot,
    ) -> tuple[AnswerItem, ...]: ...


@runtime_checkable
class RetrieverProtocol(Protocol):
    def candidates(self, ctx: AuthorizedContext, selector: Selector, snapshot: Snapshot) -> CandidateSet: ...


# ---------------------------------------------------------------------------
# Write request / transport
# ---------------------------------------------------------------------------


class WriteRequest(StrictModel):
    """Client payload. Authorization fields are NEVER accepted from the body."""

    op_id: str
    key: FactKey | None = None
    text: str = ""
    value: Any = None
    value_type: str = "scalar"
    unit: str | None = None
    kind: ClaimKind = ClaimKind.ASSERTION
    source_contract: SourceContract = SourceContract.FIRST_PARTY_DECLARED
    source_id: str = ""
    source_revision: str = ""
    valid_from: str | None = None
    valid_to: str | None = None
    expected_head: str | None = None
    observed_seq: int = 0
    idempotency_key: str = ""
    request_digest: str = ""

    @model_validator(mode="after")
    def _structured_or_text(self) -> WriteRequest:
        if self.key is None and not self.text.strip():
            raise ValueError("a write needs a structured key or sanitized text")
        if not self.op_id or not self.idempotency_key:
            raise ValueError("op_id and idempotency_key are required")
        return self


class Limits(StrictModel):
    scope: str
    plan_revision: str
    plan_label: str
    active_facts: int
    fact_capacity: int
    events: int
    event_capacity: int
    pending: int
    jobs: int
    bytes_: int = Field(default=0, alias="bytes")
    price: None = None
    evidence_status: Literal["measured", "unmeasured"] = "unmeasured"
