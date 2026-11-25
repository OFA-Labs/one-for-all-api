"""E-Brain benchmark contract (harness API v1).

Every contender (the three team prototypes and the Control) ships a module
``adapter.py`` that defines ``class Adapter`` satisfying :class:`AdapterProtocol`.
The harness drives every contender through exactly these calls, on the same
seeded data, on the same machine.

Rules for adapters (enforced by review and by the harness where possible):
  * Python 3.11 standard library only (``sqlite3`` included). No network,
    no third-party packages, no model downloads.
  * Deterministic: no wall-clock reads and no unseeded randomness. Use the
    ``ts`` values passed in. ``config["seed"]`` is provided.
  * All durable state lives under ``workdir``. A new ``Adapter(workdir)`` on
    the same folder must see every write that was acknowledged before.
  * Two ``Adapter`` instances in two processes may share one ``workdir`` at
    the same time (Claude and Codex writing concurrently).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

HARNESS_API_VERSION = "1.0.0"

Kind = Literal[
    "spec", "code", "skill", "log", "claim",
    "decision", "dependency", "task", "summary",
]
Authority = Literal["human", "verified", "agent"]
Provenance = Literal["first_party", "external"]
Visibility = Literal["shared", "private"]
Status = Literal[
    "current", "superseded", "conflicted", "stale", "quarantined", "unknown",
]

KINDS: tuple[str, ...] = (
    "spec", "code", "skill", "log", "claim",
    "decision", "dependency", "task", "summary",
)
AUTHORITY_RANK: dict[str, int] = {"agent": 0, "verified": 1, "human": 2}
STATUSES: tuple[str, ...] = (
    "current", "superseded", "conflicted", "stale", "quarantined", "unknown",
)


@dataclass(frozen=True)
class Write:
    """One memory write from one agent.

    op_id       Globally unique. Re-sending an identical Write is a no-op.
                Re-sending an op_id with different content MUST be rejected.
    ts          Logical time in seconds since project start. Writes with the
                same ts from different agents are concurrent.
    agent_id    "claude" | "codex" | "voice" (the harness may add others).
    project_id  Tenant boundary. A query never sees another project's data.
    visibility  "private" writes are visible only to the same agent_id.
    kind        See ``KINDS``.
    text        Free text, 1..20_000 characters.
    path        Natural key of a file-like artifact (spec/code/skill/log),
                else None.
    authority   Who asserts it: human user > verified (backed by a test or an
                artifact) > agent inference.
    provenance  "external" = derived from untrusted content (web page,
                uploaded file, tool output, worker report).
    supersedes  op_ids the writer explicitly replaces (its view of "current").
                Often empty even for real updates ("silent updates").
    deleted     Tombstone: the artifact at ``path`` (and the ops listed in
                ``supersedes``) no longer exists.
    """

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
    """A request for context.

    token_budget  Maximum proxy tokens allowed in ``Bundle.rendered``
                  (see ``harness.tokens.count_tokens``).
    as_of         Time travel: answer as the project stood at the end of this
                  ts. None means "now" (= ``ts``).
    """

    query_id: str
    ts: int
    agent_id: str
    project_id: str
    text: str
    token_budget: int
    as_of: int | None = None


@dataclass(frozen=True)
class Item:
    """One unit of context returned to an agent.

    text            What the agent sees. Restating is allowed, but value codes
                    (tokens like ``VC-7Q2KX9``) MUST be kept verbatim.
    status          The adapter's claim about this item's currency.
    source_op_ids   Provenance. Non-empty; every id must be an accepted write
                    visible to the querying agent. Every value code in
                    ``text`` must occur in at least one cited write.
    flags           Free labels; the harness reads "untrusted" and "conflict".
    """

    item_id: str
    text: str
    status: Status
    source_op_ids: tuple[str, ...]
    flags: tuple[str, ...] = ()
    score: float = 0.0


@dataclass(frozen=True)
class Bundle:
    """The assembled context.

    items     Ordered, most important first.
    rendered  The exact text that would be injected into the agent's
              context. It MUST show every item's status, MUST mark untrusted
              items, and MUST NOT contain any value code that is absent from
              ``items``. Its proxy token count MUST be <= token_budget.
    """

    items: tuple[Item, ...]
    rendered: str


@dataclass(frozen=True)
class Trace:
    """A usage signal reported after an agent session.

    shown     item_ids that were in the agent's context.
    followed  item_ids the agent acted in line with.
    ignored   item_ids the agent acted against.
    note      Free-text session outcome; may carry a correction (for example
              a new value code and the path where it was observed).
    """

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
    """What a self-heal cycle did. Each action is a dict with at least
    ``{"action": str, "targets": list[str], "reason": str}``."""

    actions: tuple[dict, ...] = field(default_factory=tuple)


@runtime_checkable
class AdapterProtocol(Protocol):
    name: str

    def __init__(self, workdir: str, config: dict | None = None) -> None: ...

    def write(self, w: Write) -> WriteAck: ...

    def query(self, q: Query) -> Bundle: ...

    def observe(self, t: Trace) -> None: ...

    def maintain(self, now: int) -> MaintainReport: ...

    def rollback(self, to_ts: int) -> None:
        """Revert the brain to exactly how it stood at the end of ``to_ts``:
        undo every write and every maintenance action after it."""
        ...

    def close(self) -> None: ...
