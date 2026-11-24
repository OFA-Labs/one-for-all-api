"""E-Brain data types (self-contained copy of the frozen benchmark contract v1.0.0, plus helpers).

Field names and meanings equal ``benchmark/harness/api.py`` so the store also runs under the
benchmark harness (which duck-types). Named ``models`` (not ``types``) to avoid shadowing stdlib.
Tenant: ``user_id`` is NOT a dataclass field; it is fixed per ``Store`` instance (see store.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

API_VERSION = "1.0.0"
Kind = Literal["spec", "code", "skill", "log", "claim", "decision", "dependency", "task", "summary"]
Authority = Literal["human", "verified", "agent"]
Provenance = Literal["first_party", "external"]
Visibility = Literal["shared", "private"]
Status = Literal["current", "superseded", "conflicted", "stale", "quarantined", "unknown"]
KINDS: tuple[str, ...] = ("spec", "code", "skill", "log", "claim", "decision", "dependency",
                          "task", "summary")
AUTHORITY_RANK: dict[str, int] = {"agent": 0, "verified": 1, "human": 2}
STATUSES: tuple[str, ...] = ("current", "superseded", "conflicted", "stale", "quarantined",
                             "unknown")
_TOK_RE = re.compile(r"\w+|[^\w\s]")


def count_tokens(s: str) -> int:
    """Proxy token count: each run of word chars or each other non-space char is one token."""
    return len(_TOK_RE.findall(s))


@dataclass(frozen=True)
class Write:
    op_id: str
    ts: int
    agent_id: str
    project_id: str
    visibility: Visibility
    kind: Kind
    text: str
    path: str | None = None
    authority: Authority = "agent"
    provenance: Provenance = "first_party"
    supersedes: tuple[str, ...] = ()
    deleted: bool = False


@dataclass(frozen=True)
class WriteAck:
    accepted: bool
    reason: str = ""


@dataclass(frozen=True)
class Query:
    query_id: str
    ts: int
    agent_id: str
    project_id: str
    text: str
    token_budget: int
    as_of: int | None = None


@dataclass(frozen=True)
class Item:
    item_id: str
    text: str
    status: Status
    source_op_ids: tuple[str, ...]
    flags: tuple[str, ...] = ()
    score: float = 0.0


@dataclass(frozen=True)
class Bundle:
    items: tuple[Item, ...]
    rendered: str


@dataclass(frozen=True)
class Trace:
    session_id: str
    ts: int
    agent_id: str
    project_id: str
    shown: tuple[str, ...] = ()
    followed: tuple[str, ...] = ()
    ignored: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True)
class MaintainReport:
    actions: tuple[dict, ...] = field(default_factory=tuple)


@runtime_checkable
class AdapterProtocol(Protocol):
    name: str

    def write(self, w: Write) -> WriteAck: ...
    def query(self, q: Query) -> Bundle: ...
    def observe(self, t: Trace) -> None: ...
    def maintain(self, now: int) -> MaintainReport: ...
    def rollback(self, to_ts: int) -> None: ...
    def close(self) -> None: ...
