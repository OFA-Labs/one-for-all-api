"""Independent, test-owned oracle (no product import, no product rules copied).

The oracle derives every expected identity, decision, current set, per-fact
state and temporal cut from the *public* event stream using its own explicit
rules. These rules are deliberately independent of ``ebrain/`` identity,
resolver and classifier code.

Test-owned rules (applied in ``seq`` / arrival order):

R1 LATE      an event whose valid ``ts`` is older than the greatest ``ts``
             already observed for that qualified key is accepted but cannot
             become current: decision ``accepted_noncurrent``.
R2 FUTURE    an event with ``ts > as_of`` is not visible at that cut:
             decision ``accepted_pending``.
R3 CONFLICT  two or more admitted events in one ``ts`` group with the same
             supersedes base, equal authority and different sources are a
             genuine conflict: every member gets decision ``conflict`` and no
             scalar current is produced until a later event wins.
R4 WINNER    otherwise the highest-authority event at the newest ``ts`` wins;
             a tie is broken by the greatest arrival ``seq``. An explicit
             ``supersedes`` of any earlier event of the key admits a revision
             even when its authority is lower than the prior head.
R5 ERASE     a latest admitted ``erase`` ends the chain: state ``withdrawn``
             with no scalar current.
R6 SCOPE     a query sees only events whose ``scope`` equals its scope; other
             keys are reported as ``absent`` and never enter the current set.

Hidden fact labels are computed inside this module from a test-only salt and
are NEVER written to generator output or adapter inputs. They are used only
to prove (in EV-LABELS) that a contender did not receive oracle ground truth.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import groupby
from typing import Any, Iterable

from . import manifest

LABEL_SALT = "ebrain-v3-eval-oracle-label-salt-test-only"
AUTHORITY_RANK = {"agent": 0, "verified": 1, "human": 2}

STATE_ABSENT = "absent"
STATE_CURRENT = "current"
STATE_CONFLICT = "conflict"
STATE_WITHDRAWN = "withdrawn"
STATE_PENDING = "pending_verification"
STATE_FUTURE = "future"
STATE_UNKNOWN = "unknown"


def hidden_label(key: str) -> str:
    """Oracle-private identity label, derived from a test-owned salt."""
    return "H-" + hashlib.sha256(
        f"{LABEL_SALT}|{key}".encode("utf-8")).hexdigest()[:12]


@dataclass(frozen=True)
class HistoryEvent:
    seq: int
    op_id: str
    ts: int
    action: str
    key: str
    scope: str
    source: str
    authority: str
    value: str | None
    revision: int
    supersedes: tuple[str, ...]
    history: tuple[dict[str, Any], ...]
    facets: dict[str, str]
    scenario: str

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> "HistoryEvent":
        return cls(
            seq=int(d["seq"]), op_id=str(d["op_id"]), ts=int(d["ts"]),
            action=str(d["action"]), key=str(d["key"]), scope=str(d["scope"]),
            source=str(d["source"]), authority=str(d["authority"]),
            value=d.get("value"), revision=int(d.get("revision", 1)),
            supersedes=tuple(d.get("supersedes") or ()),
            history=tuple(d.get("history") or ()),
            facets=dict(d.get("facets") or {}), scenario=str(d["scenario"]),
        )


@dataclass(frozen=True)
class FactView:
    key: str
    state: str
    value: str | None
    hidden: str
    provenance: tuple[str, ...]
    facets: dict[str, str]
    valid_from: int | None
    valid_to: int | None

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "state": self.state,
            "value": self.value,
            "hidden_label": self.hidden,
            "provenance": list(self.provenance),
            "facets": dict(self.facets),
            "valid_from": self.valid_from,
            "valid_to": self.valid_to,
        }


@dataclass
class Expected:
    scope: str
    as_of: int
    knowledge_seq: int
    current_set: dict[str, FactView]
    states: dict[str, str]
    decisions: dict[str, str]
    cuts: dict[str, int]
    all_keys: tuple[str, ...]

    @property
    def all_facts(self) -> dict[str, FactView]:
        """Views for every observed key (including non-current ones)."""
        return {k: FactView(k, self.states[k], None, hidden_label(k), (), {},
                            None, None) for k in self.all_keys}

    def to_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "scope": self.scope,
            "as_of": self.as_of,
            "knowledge_seq": self.knowledge_seq,
            "current_set": {k: self.current_set[k].to_json()
                            for k in sorted(self.current_set)},
            "states": dict(sorted(self.states.items())),
            "decisions": dict(sorted(self.decisions.items())),
            "cuts": dict(sorted(self.cuts.items())),
            "all_keys": list(self.all_keys),
        }
        body["oracle_hash"] = manifest.sha256_json(body)
        return body

    @property
    def oracle_hash(self) -> str:
        return str(self.to_json()["oracle_hash"])


def _rank(authority: str) -> int:
    return AUTHORITY_RANK.get(authority, -1)


def evaluate(events: Iterable[dict[str, Any]], *, scope: str,
             as_of: int) -> Expected:
    """Compute the complete expected view for one scope and knowledge cut."""
    ingests = sorted((HistoryEvent.from_json(e) for e in events),
                     key=lambda e: e.seq)
    decisions: dict[str, str] = {}
    max_ts: dict[str, int] = {}
    admitted: dict[str, list[HistoryEvent]] = {}

    for ev in ingests:                                   # R1, R2
        prior = max_ts.get(ev.key)
        if prior is not None and ev.ts < prior:
            decisions[ev.op_id] = "accepted_noncurrent"
        elif ev.ts > as_of:
            decisions[ev.op_id] = "accepted_pending"
        else:
            decisions[ev.op_id] = "applied"
            admitted.setdefault(ev.key, []).append(ev)
        max_ts[ev.key] = ev.ts if prior is None else max(prior, ev.ts)

    winners: dict[str, HistoryEvent | None] = {}
    conflict_keys: set[str] = set()
    for key, evs in admitted.items():                    # R3, R4
        remaining: list[HistoryEvent] = []
        for ts, group_iter in groupby(sorted(evs, key=lambda e: e.ts),
                                      key=lambda e: e.ts):
            group = list(group_iter)
            bases = {frozenset(e.supersedes) for e in group}
            authorities = {e.authority for e in group}
            sources = {e.source for e in group}
            if (len(group) > 1 and len(bases) == 1 and len(authorities) == 1
                    and len(sources) > 1):
                for e in group:
                    decisions[e.op_id] = "conflict"
                conflict_keys.add(key)
                continue
            best = max(group, key=lambda e: (_rank(e.authority), e.seq))
            remaining.append(best)
        winners[key] = max(remaining, key=lambda e: (e.ts, e.seq)) \
            if remaining else None

    states: dict[str, str] = {}
    current: dict[str, FactView] = {}
    cuts: dict[str, int] = {}
    all_keys = sorted({e.key for e in ingests})

    for key in all_keys:
        evs = sorted(admitted.get(key, []), key=lambda e: (e.ts, e.seq))
        cuts[key] = max((e.ts for e in evs),
                        default=max_ts.get(key, evs[0].ts if evs else as_of))
        scoped = [e for e in evs if e.scope == scope]
        if not scoped and any(e.scope != scope for e in ingests if e.key == key):
            states[key] = STATE_ABSENT                   # R6
            continue
        if not scoped:
            states[key] = STATE_FUTURE if max_ts.get(key, 0) > as_of \
                else STATE_UNKNOWN
            continue
        winner = winners.get(key)
        last = max(scoped, key=lambda e: (e.ts, e.seq))
        if last.action == "erase" and winner is not None \
                and winner.op_id == last.op_id:         # R5
            states[key] = STATE_WITHDRAWN
        elif key in conflict_keys and winner is None:
            states[key] = STATE_CONFLICT
        elif winner is not None and winner.scope == scope:
            states[key] = STATE_CURRENT
            current[key] = FactView(
                key=key, state=STATE_CURRENT, value=winner.value,
                hidden=hidden_label(key), provenance=(winner.op_id,),
                facets=dict(winner.facets), valid_from=winner.ts,
                valid_to=None,
            )
        elif key in conflict_keys:
            states[key] = STATE_CONFLICT
        else:
            states[key] = STATE_PENDING

    knowledge_seq = max((e.seq for e in ingests if e.ts <= as_of), default=0)
    return Expected(
        scope=scope, as_of=as_of, knowledge_seq=knowledge_seq,
        current_set=current, states=states, decisions=decisions, cuts=cuts,
        all_keys=tuple(all_keys),
    )


def review_table(events: Iterable[dict[str, Any]],
                 expected: Expected) -> list[dict[str, Any]]:
    """Human-reviewable per-event table for miniature histories."""
    rows = []
    for d in sorted(events, key=lambda e: e["seq"]):
        rows.append({
            "seq": d["seq"],
            "op_id": d["op_id"],
            "ts": d["ts"],
            "key": d["key"],
            "scope": d["scope"],
            "decision": expected.decisions.get(d["op_id"], "unknown"),
            "state_after": expected.states.get(d["key"], STATE_UNKNOWN),
        })
    return rows


def hidden_labels_for(events: Iterable[dict[str, Any]]) -> set[str]:
    return {hidden_label(str(e["key"])) for e in events}


__all__ = [
    "LABEL_SALT", "AUTHORITY_RANK", "STATE_ABSENT", "STATE_CURRENT",
    "STATE_CONFLICT", "STATE_WITHDRAWN", "STATE_PENDING", "STATE_FUTURE",
    "STATE_UNKNOWN", "hidden_label", "HistoryEvent", "FactView", "Expected",
    "evaluate", "review_table", "hidden_labels_for",
]
