"""Control contender: the null hypothesis a team must measurably beat.

What a competent engineer builds in one day from the public contract only:

Store      sqlite3 under ``workdir`` (WAL, busy_timeout, synchronous=NORMAL:
           survives a process kill). Table ``ops`` is the source of truth;
           ``actions`` holds maintenance actions with their ts; ``traces``
           stores usage traces. Writes are transactional (BEGIN IMMEDIATE),
           idempotent on an identical op_id, and reject op_id reuse with
           different content and malformed writes.
Index      hierarchical: project -> visibility/agent -> kind -> path
           (composite sqlite index plus the in-memory path map).
Versions   only authoritative metadata, replayed in (ts, seq) order:
           * an op listed in a later op's ``supersedes`` is superseded;
           * a later op at the same ``path`` supersedes the earlier one,
             unless it has lower authority (then the newcomer loses);
           * a tombstone ends its path;
           * same ts + same path (or same superseded base) from different
             agents with equal authority -> both ``conflicted``;
           * ``supersedes`` naming an already-superseded op (stale base) ->
             the newcomer is ``conflicted`` and the head stays current;
           * external ops are flagged ``untrusted`` and never override
             first-party ops (they are ``quarantined`` if they try).
           No semantic linking of free-text claims: two claims about the same
           subject without path/supersedes both stay current.
Retrieval  BM25 (sqlite FTS5; pure-Python BM25 if FTS5 is missing) plus a
           hashed character-trigram TF-IDF cosine, fused by reciprocal rank
           fusion (k=60), recency as tie-breaker.
Budget     greedy fill in rank order; long texts are cut to the lines that
           best match the query; one line per item
           ``[status|flags] text (src: op_id)``.
Lifecycle  ``maintain()`` rebuilds statuses from the store, archives logs
           older than a fixed horizon (hidden unless the query mentions
           logs) and hides exact-duplicate texts. Traces are stored, unused.
Time       every derived edge and action carries a ts: ``as_of`` filters by
           ts; ``rollback`` deletes ops/actions/traces after ``to_ts``.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import zlib
from collections import defaultdict
from dataclasses import dataclass

from harness.api import (AUTHORITY_RANK, KINDS, Bundle, Item, MaintainReport,
                         Query, Trace, Write, WriteAck)
from harness.tokens import count_tokens

LOG_HORIZON = 1500
RRF_K = 60
CANDIDATES = 150
SNIPPET_TOKENS = 60
WORD_RE = re.compile(r"[a-z0-9]+")
STOP = set("a an the is are was were be of to for in on at and or what "
           "which who how do does did we our us it its this that now right "
           "current currently use used using me my remind settle settled "
           "value whats s".split())
PREC = {"superseded": 3, "quarantined": 2, "conflicted": 1}
SCHEMA = """
CREATE TABLE IF NOT EXISTS ops(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, op_id TEXT UNIQUE NOT NULL,
  ts INTEGER NOT NULL, agent TEXT, project TEXT, visibility TEXT, kind TEXT,
  path TEXT, authority TEXT, provenance TEXT, supersedes TEXT,
  deleted INTEGER, text TEXT, digest TEXT);
CREATE INDEX IF NOT EXISTS ops_hier
  ON ops(project, visibility, agent, kind, path);
CREATE TABLE IF NOT EXISTS actions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, action TEXT,
  op_id TEXT, info TEXT);
CREATE TABLE IF NOT EXISTS traces(
  session_id TEXT, ts INTEGER, body TEXT);
"""


@dataclass
class _Op:
    seq: int
    op_id: str
    ts: int
    agent: str
    project: str
    visibility: str
    kind: str
    path: str | None
    authority: str
    provenance: str
    supersedes: tuple[str, ...]
    deleted: bool
    text: str

    @property
    def rank(self) -> int:
        return AUTHORITY_RANK.get(self.authority, 0)


def _digest(w: Write) -> str:
    body = json.dumps([w.ts, w.agent_id, w.project_id, w.visibility, w.kind,
                       w.text, w.path, w.authority, w.provenance,
                       list(w.supersedes), bool(w.deleted)])
    return hashlib.sha256(body.encode()).hexdigest()


def _validate(w: Write) -> str:
    if not isinstance(w.op_id, str) or not w.op_id:
        return "bad op_id"
    if not isinstance(w.text, str) or not 1 <= len(w.text) <= 20000:
        return "text must be 1..20000 characters"
    if w.kind not in KINDS:
        return f"bad kind {w.kind!r}"
    if w.authority not in AUTHORITY_RANK:
        return "bad authority"
    if w.provenance not in ("first_party", "external"):
        return "bad provenance"
    if w.visibility not in ("shared", "private"):
        return "bad visibility"
    if not isinstance(w.ts, int) or w.ts < 0:
        return "bad ts"
    if not w.agent_id or not w.project_id:
        return "missing agent or project"
    return ""


def _terms(text: str) -> list[str]:
    return [t for t in WORD_RE.findall(text.lower()) if t not in STOP]


def _trigrams(text: str) -> dict[int, int]:
    out: dict[int, int] = defaultdict(int)
    for word in WORD_RE.findall(text[:2000].lower()):
        padded = f" {word} "
        for i in range(len(padded) - 2):
            out[zlib.crc32(padded[i:i + 3].encode()) & 0xFFFFF] += 1
    return out


class _Derived:
    """Statuses derived by replaying ops in (ts, seq) order."""

    def __init__(self) -> None:
        self.ops: dict[str, _Op] = {}
        self.edges: dict[str, list[tuple[int, str]]] = defaultdict(list)
        self.sup_by: dict[str, str] = {}
        self.path_live: dict[tuple[str, str], list[str]] = defaultdict(list)
        self.last_ts = -1

    def _edge(self, op: str, status: str, ts: int) -> None:
        self.edges[op].append((ts, status))

    def _supersede(self, op: str, by: _Op) -> None:
        if op not in self.sup_by:
            self.sup_by[op] = by.op_id
            self._edge(op, "superseded", by.ts)
        o = self.ops[op]
        if o.path:
            live = self.path_live[(o.project, o.path)]
            if op in live:
                live.remove(op)

    def apply(self, w: _Op) -> None:
        self.ops[w.op_id] = w
        self.last_ts = max(self.last_ts, w.ts)
        targets = [s for s in w.supersedes
                   if s in self.ops and self.ops[s].project == w.project]
        key = (w.project, w.path) if w.path else None
        if w.deleted:
            for s in targets + (list(self.path_live[key]) if key else []):
                self._supersede(s, w)
            return
        ext = w.provenance == "external"
        if ext and (any(self.ops[s].provenance == "first_party"
                        for s in targets) or (key and any(
                            self.ops[p].provenance == "first_party"
                            for p in self.path_live[key]))):
            self._edge(w.op_id, "quarantined", w.ts)
            return
        stale = False
        for s in targets:
            by = self.sup_by.get(s)
            if by is None:
                continue
            x = self.ops[by]
            if x.ts == w.ts and x.agent != w.agent and x.rank == w.rank:
                self._edge(x.op_id, "conflicted", w.ts)
                self._edge(w.op_id, "conflicted", w.ts)
            else:
                stale = True
        if stale:
            self._edge(w.op_id, "conflicted", w.ts)
            return
        for s in targets:
            self._supersede(s, w)
        if key is None:
            return
        lost = False
        for p in list(self.path_live[key]):
            prev = self.ops[p]
            if (prev.ts == w.ts and prev.agent != w.agent
                    and prev.rank == w.rank):
                self._edge(p, "conflicted", w.ts)
                self._edge(w.op_id, "conflicted", w.ts)
            elif w.rank >= prev.rank:
                self._supersede(p, w)
            else:
                lost = True
        if lost:
            self.sup_by[w.op_id] = w.op_id
            self._edge(w.op_id, "superseded", w.ts)
        else:
            self.path_live[key].append(w.op_id)

    def status(self, op: str, t: int) -> str:
        best = "current"
        for ts, st in self.edges.get(op, ()):
            if ts <= t and PREC[st] > PREC.get(best, 0):
                best = st
        return best


class Adapter:
    name = "control"

    def __init__(self, workdir: str, config: dict | None = None) -> None:
        os.makedirs(workdir, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(workdir, "control.db"),
                                  timeout=30, isolation_level=None,
                                  check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        try:
            self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts "
                            "USING fts5(text)")
            self.fts = True
        except sqlite3.OperationalError:
            self.fts = False
        self._reload()

    # ------------------------------------------------------------ state
    def _reload(self) -> None:
        self.d = _Derived()
        self.loaded_seq = 0
        self.tri: dict[str, dict[int, int]] = {}
        self.tri_norm: dict[str, float] = {}
        self.post: dict[int, list[str]] = defaultdict(list)
        self.bm_post: dict[str, dict[str, int]] = defaultdict(dict)
        self.bm_len: dict[str, int] = {}
        self.hidden: dict[str, list[tuple[int, str]]] = defaultdict(list)
        self._sync(force=True)
        for ts, action, op in self.db.execute(
                "SELECT ts, action, op_id FROM actions"):
            self.hidden[op].append((ts, action))

    def _row_op(self, r: tuple) -> _Op:
        return _Op(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8],
                   r[9], tuple(json.loads(r[10])), bool(r[11]), r[12])

    def _index(self, op: _Op) -> None:
        vec = _trigrams(op.text)
        self.tri[op.op_id] = vec
        self.tri_norm[op.op_id] = math.sqrt(sum(v * v for v in vec.values()))
        for g in vec:
            self.post[g].append(op.op_id)
        if not self.fts:
            terms = _terms(op.text)
            self.bm_len[op.op_id] = len(terms)
            for t in terms:
                self.bm_post[t][op.op_id] = self.bm_post[t].get(op.op_id,
                                                                0) + 1

    def _sync(self, force: bool = False) -> None:
        """Pick up rows written by this or another instance/process."""
        top = self.db.execute("SELECT COALESCE(MAX(seq), 0) FROM ops"
                              ).fetchone()[0]
        if top < self.loaded_seq:
            self._reload()
            return
        if top == self.loaded_seq and not force:
            return
        rows = [self._row_op(r) for r in self.db.execute(
            "SELECT seq, op_id, ts, agent, project, visibility, kind, path, "
            "authority, provenance, supersedes, deleted, text FROM ops "
            "WHERE seq > ? ORDER BY ts, seq", (self.loaded_seq,))]
        if rows and rows[0].ts < self.d.last_ts:
            self._rebuild_status()
        else:
            for op in rows:
                self.d.apply(op)
        for op in rows:
            self._index(op)
        self.loaded_seq = top

    def _rebuild_status(self) -> None:
        d = _Derived()
        for r in self.db.execute(
                "SELECT seq, op_id, ts, agent, project, visibility, kind, "
                "path, authority, provenance, supersedes, deleted, text "
                "FROM ops ORDER BY ts, seq"):
            d.apply(self._row_op(r))
        self.d = d

    # ------------------------------------------------------------ write
    def write(self, w: Write) -> WriteAck:
        why = _validate(w)
        if why:
            return WriteAck(False, why)
        dig = _digest(w)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT digest FROM ops WHERE op_id=?",
                                  (w.op_id,)).fetchone()
            if row is not None:
                self.db.execute("COMMIT")
                if row[0] == dig:
                    return WriteAck(True, "duplicate op_id (no-op)")
                return WriteAck(False, "op_id reused with different content")
            cur = self.db.execute(
                "INSERT INTO ops(op_id, ts, agent, project, visibility, kind, "
                "path, authority, provenance, supersedes, deleted, text, "
                "digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (w.op_id, w.ts, w.agent_id, w.project_id, w.visibility,
                 w.kind, w.path, w.authority, w.provenance,
                 json.dumps(list(w.supersedes)), int(w.deleted), w.text, dig))
            if self.fts:
                self.db.execute("INSERT INTO fts(rowid, text) VALUES (?, ?)",
                                (cur.lastrowid, w.text))
            self.db.execute("COMMIT")
        except Exception:
            self.db.execute("ROLLBACK")
            raise
        self._sync()
        return WriteAck(True)

    # ------------------------------------------------------------ query
    def _visible(self, op: _Op, q: Query, t: int) -> bool:
        return (op.project == q.project_id and op.ts <= t
                and (op.visibility == "shared" or op.agent == q.agent_id))

    def _bm25(self, q: Query, terms: list[str], t: int) -> list[str]:
        if not terms:
            return []
        if self.fts:
            match = " OR ".join(f'"{x}"' for x in dict.fromkeys(terms))
            rows = self.db.execute(
                "SELECT o.op_id FROM fts JOIN ops o ON o.seq = fts.rowid "
                "WHERE fts MATCH ? AND o.project = ? AND o.ts <= ? AND "
                "(o.visibility = 'shared' OR o.agent = ?) AND o.deleted = 0 "
                "ORDER BY bm25(fts) LIMIT ?",
                (match, q.project_id, t, q.agent_id, CANDIDATES)).fetchall()
            return [r[0] for r in rows]
        n = max(1, len(self.bm_len))
        avg = sum(self.bm_len.values()) / n
        score: dict[str, float] = defaultdict(float)
        for term in set(terms):
            post = self.bm_post.get(term, {})
            idf = math.log(1 + (n - len(post) + 0.5) / (len(post) + 0.5))
            for op, tf in post.items():
                dl = self.bm_len[op]
                score[op] += idf * tf * 2.2 / (tf + 1.2 * (
                    0.25 + 0.75 * dl / avg))
        ranked = sorted(score, key=lambda o: -score[o])
        return [o for o in ranked if self._visible(self.d.ops[o], q, t)
                and not self.d.ops[o].deleted][:CANDIDATES]

    def _trigram(self, q: Query, t: int) -> list[str]:
        qv = _trigrams(q.text)
        n = max(1, len(self.tri))
        score: dict[str, float] = defaultdict(float)
        qn = 0.0
        for g, qtf in qv.items():
            post = self.post.get(g, ())
            if not post or len(post) > 0.3 * n:
                continue
            idf = math.log(n / len(post))
            qn += (qtf * idf) ** 2
            for op in post:
                score[op] += qtf * idf * idf * self.tri[op][g]
        if not score:
            return []
        ranked = sorted(score, key=lambda o: -score[o] / (
            self.tri_norm[o] or 1.0))
        out = []
        for o in ranked:
            op = self.d.ops[o]
            if self._visible(op, q, t) and not op.deleted:
                out.append(o)
                if len(out) >= CANDIDATES:
                    break
        return out

    def _hidden(self, op: str, t: int, logs_ok: bool) -> bool:
        for ts, action in self.hidden.get(op, ()):
            if ts <= t and (action == "dedupe" or not logs_ok):
                return True
        return False

    @staticmethod
    def _snippet(text: str, terms: set[str]) -> str:
        if count_tokens(text) <= SNIPPET_TOKENS:
            return text
        lines = [ln for ln in text.splitlines() if ln.strip()]
        ranked = sorted(range(len(lines)), key=lambda i: (
            -len(terms & set(_terms(lines[i]))), i))
        keep, used = [], 0
        for i in ranked:
            c = count_tokens(lines[i])
            if used + c > SNIPPET_TOKENS and keep:
                break
            keep.append(i)
            used += c
        return " / ".join(lines[i] for i in sorted(keep))

    def query(self, q: Query) -> Bundle:
        self._sync()
        t = q.as_of if q.as_of is not None else q.ts
        terms = _terms(q.text)
        fused: dict[str, float] = defaultdict(float)
        for ranked in (self._bm25(q, terms, t), self._trigram(q, t)):
            for i, op in enumerate(ranked):
                fused[op] += 1.0 / (RRF_K + i + 1)
        order = sorted(fused, key=lambda o: (-fused[o], -self.d.ops[o].ts,
                                             o))
        logs_ok = bool({"log", "logs"} & set(WORD_RE.findall(
            q.text.lower())))
        tset = set(terms)
        items, lines, used = [], [], 0
        for op_id in order[:80]:
            op = self.d.ops[op_id]
            st = self.d.status(op_id, t)
            if st in ("superseded", "quarantined"):
                continue
            if self._hidden(op_id, t, logs_ok or op.kind != "log"):
                continue
            flags = []
            if op.provenance == "external":
                flags.append("untrusted")
            if st == "conflicted":
                flags.append("conflict")
            text = self._snippet(op.text, tset)
            label = st + ("|" + ",".join(flags) if flags else "")
            line = f"[{label}] {text} (src: {op_id})"
            cost = count_tokens(line)
            if used + cost > q.token_budget:
                continue
            used += cost
            lines.append(line)
            items.append(Item(op_id, text, st, (op_id,), tuple(flags),
                              round(fused[op_id], 6)))
        return Bundle(tuple(items), "\n".join(lines))

    # -------------------------------------------------------- lifecycle
    def observe(self, t: Trace) -> None:
        body = json.dumps({"agent": t.agent_id, "project": t.project_id,
                           "shown": list(t.shown),
                           "followed": list(t.followed),
                           "ignored": list(t.ignored), "note": t.note})
        self.db.execute("INSERT INTO traces VALUES (?, ?, ?)",
                        (t.session_id, t.ts, body))

    def maintain(self, now: int) -> MaintainReport:
        self._sync()
        self._rebuild_status()
        archived, deduped = [], []
        first_text: dict[tuple, str] = {}
        for op in sorted(self.d.ops.values(), key=lambda o: (o.ts, o.seq)):
            if op.ts > now or op.deleted:
                continue
            done = {a for _, a in self.hidden.get(op.op_id, ())}
            if (op.kind == "log" and op.ts < now - LOG_HORIZON
                    and "archive" not in done):
                archived.append(op.op_id)
            norm = " ".join(op.text.lower().split())
            scope = (op.project, op.visibility,
                     op.agent if op.visibility == "private" else "")
            k = (scope, hashlib.sha1(norm.encode()).hexdigest())
            if k in first_text:
                if "dedupe" not in done:
                    deduped.append(op.op_id)
            else:
                first_text[k] = op.op_id
        self.db.execute("BEGIN IMMEDIATE")
        for action, ops in (("archive", archived), ("dedupe", deduped)):
            self.db.executemany(
                "INSERT INTO actions(ts, action, op_id, info) "
                "VALUES (?,?,?,'')", [(now, action, o) for o in ops])
            for o in ops:
                self.hidden[o].append((now, action))
        self.db.execute("COMMIT")
        acts = []
        if archived:
            acts.append({"action": "archive", "targets": archived,
                         "reason": f"log older than {LOG_HORIZON}"})
        if deduped:
            acts.append({"action": "dedupe", "targets": deduped,
                         "reason": "exact duplicate text"})
        return MaintainReport(tuple(acts))

    def rollback(self, to_ts: int) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        if self.fts:
            self.db.execute("DELETE FROM fts WHERE rowid IN "
                            "(SELECT seq FROM ops WHERE ts > ?)", (to_ts,))
        self.db.execute("DELETE FROM ops WHERE ts > ?", (to_ts,))
        self.db.execute("DELETE FROM actions WHERE ts > ?", (to_ts,))
        self.db.execute("DELETE FROM traces WHERE ts > ?", (to_ts,))
        self.db.execute("COMMIT")
        self._reload()

    def close(self) -> None:
        try:
            self.db.close()
        except sqlite3.Error:
            pass
