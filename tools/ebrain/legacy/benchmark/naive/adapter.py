"""Naive floor: BM25-ish keyword top-k, every item "current", no versions.

It respects the contract (durable sqlite store, idempotent writes, malformed
rejection, project/visibility isolation, token budget) but has no version
logic, no provenance flags and no lifecycle. It exists to prove that the
metrics detect zombies.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import defaultdict

from harness.api import (AUTHORITY_RANK, KINDS, Bundle, Item, MaintainReport,
                         Query, Trace, Write, WriteAck)
from harness.tokens import count_tokens

WORD_RE = re.compile(r"[a-z0-9]+")


def _terms(text: str) -> list[str]:
    return WORD_RE.findall(text.lower())


class Adapter:
    name = "naive"

    def __init__(self, workdir: str, config: dict | None = None) -> None:
        os.makedirs(workdir, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(workdir, "naive.db"),
                                  timeout=30, isolation_level=None)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS ops(seq INTEGER PRIMARY KEY "
            "AUTOINCREMENT, op_id TEXT UNIQUE, ts INT, agent TEXT, "
            "project TEXT, visibility TEXT, deleted INT, text TEXT, "
            "digest TEXT)")
        self._load()

    def _load(self) -> None:
        self.docs: dict[str, tuple] = {}
        self.post: dict[str, dict[str, int]] = defaultdict(dict)
        self.dlen: dict[str, int] = {}
        self.seq = 0
        self._sync()

    def _sync(self) -> None:
        for r in self.db.execute(
                "SELECT seq, op_id, ts, agent, project, visibility, deleted, "
                "text FROM ops WHERE seq > ? ORDER BY seq", (self.seq,)):
            self.seq = r[0]
            self.docs[r[1]] = r[2:]
            terms = _terms(r[7])
            self.dlen[r[1]] = len(terms)
            for t in terms:
                self.post[t][r[1]] = self.post[t].get(r[1], 0) + 1

    def write(self, w: Write) -> WriteAck:
        if (not isinstance(w.text, str) or not 1 <= len(w.text) <= 20000
                or w.kind not in KINDS or w.authority not in AUTHORITY_RANK):
            return WriteAck(False, "malformed")
        dig = hashlib.sha256(json.dumps(
            [w.ts, w.agent_id, w.project_id, w.visibility, w.kind, w.text,
             w.path, w.authority, w.provenance, list(w.supersedes),
             w.deleted]).encode()).hexdigest()
        row = self.db.execute("SELECT digest FROM ops WHERE op_id=?",
                              (w.op_id,)).fetchone()
        if row is not None:
            return WriteAck(row[0] == dig, "duplicate")
        self.db.execute(
            "INSERT INTO ops(op_id, ts, agent, project, visibility, deleted, "
            "text, digest) VALUES (?,?,?,?,?,?,?,?)",
            (w.op_id, w.ts, w.agent_id, w.project_id, w.visibility,
             int(w.deleted), w.text, dig))
        self._sync()
        return WriteAck(True)

    def query(self, q: Query) -> Bundle:
        self._sync()
        t = q.as_of if q.as_of is not None else q.ts
        n = max(1, len(self.docs))
        avg = sum(self.dlen.values()) / n
        score: dict[str, float] = defaultdict(float)
        for term in set(_terms(q.text)):
            post = self.post.get(term, {})
            idf = math.log(1 + (n - len(post) + 0.5) / (len(post) + 0.5))
            for op, tf in post.items():
                score[op] += idf * tf * 2.2 / (
                    tf + 1.2 * (0.25 + 0.75 * self.dlen[op] / avg))
        items, lines, used = [], [], 0
        for op in sorted(score, key=lambda o: (-score[o], o))[:60]:
            ts, agent, project, vis, deleted, text = self.docs[op]
            if (project != q.project_id or ts > t or deleted
                    or (vis == "private" and agent != q.agent_id)):
                continue
            line = f"[current] {text} (src: {op})"
            cost = count_tokens(line)
            if used + cost > q.token_budget:
                continue
            used += cost
            lines.append(line)
            items.append(Item(op, text, "current", (op,), (), score[op]))
        return Bundle(tuple(items), "\n".join(lines))

    def observe(self, t: Trace) -> None:
        return None

    def maintain(self, now: int) -> MaintainReport:
        return MaintainReport()

    def rollback(self, to_ts: int) -> None:
        self.db.execute("DELETE FROM ops WHERE ts > ?", (to_ts,))
        self._load()

    def close(self) -> None:
        self.db.close()
