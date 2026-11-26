"""History enums, the single status-mapping function, and ingest (request) models."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STATES = ("planning", "executing", "waiting", "permission", "question", "paused", "completed",
          "declined", "cancelled", "error", "unknown")
TERMINAL_STATES = frozenset({"completed", "declined", "cancelled", "error"})
NON_HISTORY_STATES = frozenset({"planning", "executing"})
TIERS = ("A", "B", "C", "D", "unknown", "none")
EVIDENCE_STATUSES = ("verified", "submitted", "held", "unknown", "none")
DISPLAY_STATUSES = ("Verified", "Needs review", "Submitted", "Declined", "Paused", "Cancelled",
                    "Unknown", "Error")
SORTS = ("newest", "oldest")
# Must start with a letter, digit or underscore so "." and ".." can never be ids.
TASK_ID_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}$")

_PARKED = frozenset({"waiting", "permission", "question"})
_DIRECT = {"paused": "Paused", "declined": "Declined", "cancelled": "Cancelled",
           "error": "Error", "unknown": "Unknown"}


def display_status(state: str, tier: str, evidence_status: str) -> str | None:
    """The one status mapping (plan §3.3). Returns None for states History never shows.

    A Tier-D worker claim never counts, and only Tier A with verified evidence is "Verified".
    """
    if state in _PARKED:
        return "Needs review"
    if state in _DIRECT:
        return _DIRECT[state]
    if state != "completed":
        return None
    if tier == "D":
        return "Unknown"
    if tier == "A" and evidence_status == "verified":
        return "Verified"
    if evidence_status == "held" or tier == "C":
        return "Needs review"
    if tier in ("A", "B") and evidence_status in ("verified", "submitted"):
        return "Submitted"
    return "Unknown"


def is_verified(tier: str, evidence_status: str) -> bool:
    return tier == "A" and evidence_status == "verified"


Tier = Literal["A", "B", "C", "D", "unknown", "none"]
EvidenceStatus = Literal["verified", "submitted", "held", "unknown", "none"]
State = Literal["planning", "executing", "waiting", "permission", "question", "paused",
                "completed", "declined", "cancelled", "error", "unknown"]
ShortText = Field(max_length=500)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class PlanIn(_Strict):
    steps: list[str] = Field(default_factory=list, max_length=50)
    sites: list[str] = Field(default_factory=list, max_length=20)
    recipients: list[str] = Field(default_factory=list, max_length=20)


class EventIn(_Strict):
    seq: int = Field(ge=1)
    at: int = Field(ge=0)
    type: str = Field(min_length=1, max_length=64)
    message: str = Field(max_length=1000)


class EvidenceIn(_Strict):
    tier: Tier
    status: EvidenceStatus
    item_id: str | None = Field(default=None, max_length=200)
    url: str | None = Field(default=None, max_length=2000)
    readback: str | None = Field(default=None, max_length=500)
    snapshot_hash: str | None = Field(default=None, max_length=200)
    captured_at: int = Field(default=0, ge=0)
    verified_at: int | None = Field(default=None, ge=0)
    expires_at: int | None = Field(default=None, ge=0)


class TransitionIn(_Strict):
    seq: int | None = Field(default=None, ge=1)
    at: int = Field(ge=0)
    from_state: str | None = Field(default=None, alias="from", max_length=32)
    to_state: str = Field(alias="to", min_length=1, max_length=32)
    note: str | None = Field(default=None, max_length=500)


class LedgerIn(_Strict):
    idempotency_key: str = Field(min_length=1, max_length=300)
    site: str = Field(min_length=1, max_length=253)
    target: str | None = Field(default=None, max_length=300)
    action: str = Field(min_length=1, max_length=100)
    payload_hash: str = Field(min_length=1, max_length=200)
    state: Literal["intent", "committed", "verified", "unknown", "failed"]
    created_at: int = Field(default=0, ge=0)
    transitions: list[TransitionIn] = Field(default_factory=list, max_length=50)


class ApprovalIn(_Strict):
    approval_id: str | None = Field(default=None, min_length=1, max_length=200)
    page_url: str = Field(max_length=2000)
    plan_version: int = Field(ge=1)
    payload_hash: str = Field(min_length=1, max_length=200)
    exact_text: str = Field(max_length=5000)
    decision: Literal["approved", "rejected", "expired", "revoked"]
    decided_at: int = Field(ge=0)
    expires_at: int | None = Field(default=None, ge=0)
    note: str | None = Field(default=None, max_length=500)


class TaskIn(_Strict):
    """A task snapshot from the (service-only) task engine or the seed."""

    task_id: str = Field(pattern=TASK_ID_RE.pattern)
    user_id: str = Field(min_length=1, max_length=200)
    revision: int = Field(default=1, ge=1)
    goal: str = Field(max_length=2000)
    title: str = Field(min_length=1, max_length=300)
    subtitle: str = Field(default="", max_length=300)
    scenario: str = Field(default="unknown", max_length=64)
    mode: Literal["personal", "playground"] = "personal"
    state: State
    tier: Tier = "none"
    evidence_status: EvidenceStatus = "none"
    gate_reason: str | None = Field(default=None, max_length=300)
    attempt: int = Field(default=1, ge=1)
    plan_version: int = Field(default=1, ge=1)
    plan_hash: str | None = Field(default=None, max_length=200)
    plan: PlanIn = Field(default_factory=PlanIn)
    device_id: str | None = Field(default=None, max_length=200)
    result_item_id: str | None = Field(default=None, max_length=200)
    result_url: str | None = Field(default=None, max_length=2000)
    snapshot_hash: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=1000)
    is_sample: bool = False
    occurred_at: int = Field(ge=0)
    created_at: int = Field(ge=0)
    ended_at: int | None = Field(default=None, ge=0)
    events: list[EventIn] = Field(default_factory=list, max_length=500)
    evidence: EvidenceIn | None = None
    ledger: list[LedgerIn] = Field(default_factory=list, max_length=50)
    approvals: list[ApprovalIn] = Field(default_factory=list, max_length=50)
