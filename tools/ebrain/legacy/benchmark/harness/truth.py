"""Ground-truth model T1-T8 (INTERFACE.md section 2).

The generator seals, for every fact-bearing op, which chain it belongs to and
what role it plays. From the write stream plus those seals, :class:`Truth`
computes for every chain and every time t which codes are current,
conflicted or invalid. Seals never leave the harness process.

Roles
  version    a new version of the chain's fact; carries its own new code.
  copy       restates the code of an earlier version (duplicates, summaries);
             never changes chain state (T7) and shares that version's status.
  tombstone  ``deleted=True`` for the chain's path: ends the chain (T6).

Rules, applied per group of chain writes with the same ts (in stream order):
  T3  an external version never becomes current once the chain has any
      first-party version; with only external versions the latest external
      one is current and needs the ``untrusted`` flag.
  T5  a version whose ``supersedes`` names a chain op that is no longer live
      (not current, not conflicted) is stale and never becomes current.
  T2  a version with lower authority than the live value does not become
      current unless it lists a live op in ``supersedes``.
  T4  two or more surviving versions in one ts group, from different agents,
      with equal authority and equal supersedes base, are a genuine conflict:
      all become conflicted, none is current, until a later version.
  T1  otherwise the surviving version becomes the only current one and the
      previous live ops become invalid.
  T8  isolation is a property of queries, see :func:`visible`.
Ops listed in ``supersedes`` that are not in the chain (dangling ids, other
chains) are ignored.
"""
from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from itertools import groupby

from .api import AUTHORITY_RANK, Write

CODE_RE = re.compile(r"\bVC-[A-Z0-9]{6}\b")

ROLE_VERSION = "version"
ROLE_COPY = "copy"
ROLE_TOMBSTONE = "tombstone"

CURRENT = "current"
CONFLICTED = "conflicted"
INVALID = "invalid"
FUTURE = "future"
UNKNOWN = "unknown"


def find_codes(text: str) -> list[str]:
    """Return every value code in ``text`` in order of appearance."""
    return CODE_RE.findall(text)


def visible(w: Write, agent_id: str, project_id: str) -> bool:
    """T8: a query sees its own project, shared writes and its own private."""
    return w.project_id == project_id and (
        w.visibility == "shared" or w.agent_id == agent_id)


@dataclass(frozen=True)
class Seal:
    """Sealed annotation of one op (never shown to adapters)."""

    chain: str
    role: str
    code: str | None = None
    of: str | None = None  # copy: the op whose code it restates


@dataclass(frozen=True)
class Snapshot:
    """State of one chain after the ts group ``ts`` (sets of op ids)."""

    ts: int
    current: frozenset[str]
    conflicted: frozenset[str]
    invalid: frozenset[str]
    untrusted: bool
    ended: bool


class Truth:
    """Evaluates T1-T7 per chain over time; T8 via :func:`visible`."""

    def __init__(self, writes: list[Write], seals: dict[str, Seal],
                 always_invalid_codes: set[str] | None = None) -> None:
        self.seals = seals
        self.always_invalid = set(always_invalid_codes or ())
        self.ops: dict[str, Write] = {}
        by_chain: dict[str, list[Write]] = {}
        for w in sorted(writes, key=lambda x: x.ts):  # stable: stream order
            seal = seals.get(w.op_id)
            if seal is None:
                continue
            self.ops[w.op_id] = w
            by_chain.setdefault(seal.chain, []).append(w)
        self.chain_ops = {c: [w.op_id for w in ws] for c, ws in by_chain.items()}
        self._times: dict[str, list[int]] = {}
        self._snaps: dict[str, list[Snapshot]] = {}
        for chain, ws in by_chain.items():
            snaps = self._evolve(ws)
            self._snaps[chain] = snaps
            self._times[chain] = [s.ts for s in snaps]
        # code -> (chain, version op id, first ts)
        self.code_info: dict[str, tuple[str, str, int]] = {}
        for op_id, seal in seals.items():
            w = self.ops.get(op_id)
            if seal.role == ROLE_VERSION and seal.code and w is not None:
                self.code_info[seal.code] = (seal.chain, op_id, w.ts)

    # ----------------------------------------------------------- evolution
    def _evolve(self, ws: list[Write]) -> list[Snapshot]:
        chain_seen: set[str] = set()
        head: set[str] = set()
        conflicted: set[str] = set()
        invalid: set[str] = set()
        first_party_seen = False
        ended = False
        snaps: list[Snapshot] = []
        for ts, grp in groupby(ws, key=lambda w: w.ts):
            group = list(grp)
            versions = [w for w in group
                        if self.seals[w.op_id].role == ROLE_VERSION]
            tombs = [w for w in group
                     if self.seals[w.op_id].role == ROLE_TOMBSTONE]
            if ended or tombs:
                invalid |= head | conflicted | {w.op_id for w in versions}
                head, conflicted = set(), set()
                ended = True
            else:
                live = head | conflicted
                cands: list[Write] = []
                for w in versions:
                    if self._admissible(w, live, chain_seen, first_party_seen):
                        cands.append(w)
                    else:
                        invalid.add(w.op_id)
                if cands:
                    top = max(AUTHORITY_RANK[c.authority] for c in cands)
                    for c in cands:
                        if AUTHORITY_RANK[c.authority] < top:
                            invalid.add(c.op_id)
                    cands = [c for c in cands
                             if AUTHORITY_RANK[c.authority] == top]
                    bases = {frozenset(s for s in c.supersedes
                                       if s in chain_seen) for c in cands}
                    agents = {c.agent_id for c in cands}
                    invalid |= live
                    if len(cands) > 1 and len(agents) > 1 and len(bases) == 1:
                        head, conflicted = set(), {c.op_id for c in cands}
                    else:
                        winner = cands[-1]
                        invalid |= {c.op_id for c in cands[:-1]}
                        head, conflicted = {winner.op_id}, set()
            for w in group:
                chain_seen.add(w.op_id)
                if (self.seals[w.op_id].role == ROLE_VERSION
                        and w.provenance == "first_party"):
                    first_party_seen = True
            untrusted = bool(head) and all(
                self.ops[o].provenance == "external" for o in head)
            snaps.append(Snapshot(ts, frozenset(head), frozenset(conflicted),
                                  frozenset(invalid), untrusted, ended))
        return snaps

    def _admissible(self, w: Write, live: set[str], chain_seen: set[str],
                    first_party_seen: bool) -> bool:
        if w.provenance == "external" and first_party_seen:
            return False  # T3
        targets = [s for s in w.supersedes if s in chain_seen]
        if any(t not in live for t in targets):
            return False  # T5 stale base
        if live:
            top = max(AUTHORITY_RANK[self.ops[o].authority] for o in live)
            if (AUTHORITY_RANK[w.authority] < top
                    and not set(targets) & live):
                return False  # T2
        return True

    # ------------------------------------------------------------ queries
    def snapshot(self, chain: str, t: int) -> Snapshot | None:
        """Chain state at the end of ts ``t`` (None before its first op)."""
        times = self._times.get(chain)
        if not times:
            return None
        i = bisect.bisect_right(times, t) - 1
        return self._snaps[chain][i] if i >= 0 else None

    def _code(self, op_id: str) -> str | None:
        seal = self.seals.get(op_id)
        return seal.code if seal else None

    def head_codes(self, chain: str, t: int) -> list[str]:
        snap = self.snapshot(chain, t)
        if snap is None:
            return []
        return sorted(c for c in (self._code(o) for o in snap.current) if c)

    def conflicted_codes(self, chain: str, t: int) -> list[str]:
        snap = self.snapshot(chain, t)
        if snap is None:
            return []
        return sorted(c for c in (self._code(o) for o in snap.conflicted)
                      if c)

    def untrusted_required(self, chain: str, t: int) -> bool:
        snap = self.snapshot(chain, t)
        return bool(snap and snap.untrusted)

    def chain_codes(self, chain: str) -> list[str]:
        return sorted(c for c, info in self.code_info.items()
                      if info[0] == chain)

    def code_status(self, code: str, t: int) -> str:
        """current | conflicted | invalid | future | unknown at end of t."""
        if code in self.always_invalid:
            return INVALID
        info = self.code_info.get(code)
        if info is None:
            return UNKNOWN
        chain, op_id, first_ts = info
        if t < first_ts:
            return FUTURE
        snap = self.snapshot(chain, t)
        if snap is None:
            return FUTURE
        if op_id in snap.current:
            return CURRENT
        if op_id in snap.conflicted:
            return CONFLICTED
        return INVALID
