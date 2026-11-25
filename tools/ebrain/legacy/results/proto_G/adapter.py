"""Prototype G (EXPERIMENT ONLY): anchor-lock assignment + same-subject head
suppression at bundle time.

Split chains raise accuracy but leave stale heads that read as 'current' and
inflate zombie rate. This prototype keeps the split, but groups emitted items
by their chain's anchor signature and keeps only the newest item per signature
as 'current'; older same-subject fragments are shown as 'superseded'.
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store, _one_line, CODE_RE  # noqa: E402
from ebrain.models import Item  # noqa: E402

RARE_CAP = int(os.environ.get("AG1_RARE_CAP", 12))
COVERAGE_MIN = float(os.environ.get("AG1_COVERAGE_MIN", 0.85))


class Adapter(Store):
    name = "proto-G-slot-suppress"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")

    def _df_for(self, p, terms):
        out = {}
        if not terms:
            return out
        q = ",".join("?" * len(terms))
        for r in self.db.execute(f"SELECT term, COUNT(DISTINCT chain) FROM terms "
                                 f"WHERE user_id=? AND project=? AND term IN ({q}) GROUP BY term",
                                 (self.u, p, *terms)):
            out[r[0]] = r[1]
        return out

    def _anchor_map(self, p, chains, df):
        vocab = self._chain_vocab(p, chains)
        core_all = set()
        data = {}
        for c, (counts, nv) in vocab.items():
            core = self._core(counts, nv)
            core_all |= core
            data[c] = [core, set(counts)]
        for k, v in self._df_for(p, core_all).items():
            df[k] = v
        out = {}
        for c, (core, union) in data.items():
            out[c] = (frozenset(x for x in core if df.get(x, RARE_CAP + 1) <= RARE_CAP), union)
        return out

    def _assign_chain(self, w, role, codes, terms):
        db, u, p = self.db, self.u, w.project_id
        if role in ("copy", "derived", "note"):
            if not codes:
                return None, None
            r = db.execute("SELECT o.chain FROM codes c JOIN ops o ON o.user_id=c.user_id AND "
                           "o.op_id=c.op_id WHERE c.user_id=? AND c.project=? AND c.code=?",
                           (u, p, codes[0])).fetchone()
            return (r[0] if r else None), None
        targets = [r[0] for s in w.supersedes for r in db.execute(
            "SELECT chain FROM ops WHERE user_id=? AND op_id=? AND project=? AND chain IS NOT NULL",
            (u, s, p))]
        ext = w.provenance == "external"
        if w.path:
            r = db.execute("SELECT chain FROM ops WHERE user_id=? AND project=? AND path=? AND "
                           "chain IS NOT NULL ORDER BY seq LIMIT 1", (u, p, w.path)).fetchone()
            if r and not (ext and targets):
                return r[0], None
            if not targets:
                return "p:" + w.path, None
        fallback = "p:" + w.path if w.path else "c:" + w.op_id
        if role == "tomb":
            return (targets[0] if targets else fallback), None
        if targets:
            return targets[0], None
        if not terms:
            return fallback, None
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        if not cands:
            return fallback, None
        amap = self._anchor_map(p, cands, self._df_for(p, terms))
        best, best_score = None, 0.0
        for c, (anchors, union) in sorted(amap.items()):
            if anchors - terms:
                continue
            coverage = len(terms & union) / len(terms)
            if coverage < COVERAGE_MIN:
                continue
            score = len(anchors) + coverage
            if score > best_score:
                best, best_score = c, score
        return best or fallback, None

    def _items(self, q, h):
        p, out, shown = q.project_id, [], set()
        demoted = self._demoted(p, h)
        roots, open_pairs, _ = self._link_state(p, h)
        groups = {}
        for chain in self._rank(q, h):
            groups.setdefault(roots.get(chain, chain), []).append(chain)
        # collect candidate items with their signature and head timestamp
        cand = []
        for chains in groups.values():
            members = self._group_members(roots, chains[0])
            rows = self._chain_ops(p, members, h, q.agent_id)
            amap = self._anchor_map(p, members, {})
            head, conf, _ = self._evolve(rows)
            by_id = {r["op_id"]: r for r in rows}
            sig = frozenset().union(*(amap.get(c, (frozenset(), set()))[0]
                                      for c in members)) if members else frozenset()
            for oid, status in sorted([(o, "current") for o in head - demoted] +
                                      [(o, "conflicted") for o in conf]):
                r = by_id[oid]
                codes = CODE_RE.findall(r["text"])
                if not codes or codes[0] in shown:
                    continue
                shown.update(codes)
                flags = [f for f in (r["flags"] or "").split(",") if f]
                if status == "conflicted":
                    flags.append("conflict")
                if r["chain"] in open_pairs:
                    flags.append("possible_same_fact")
                line = next((ln for ln in r["text"].splitlines() if CODE_RE.search(ln)), r["text"])
                cited = [oid] + [o for c in codes for (o,) in self.db.execute(
                    "SELECT op_id FROM codes WHERE user_id=? AND project=? AND code=?",
                    (self.u, p, c)) if o != oid]
                cand.append((sig, r["ts"], oid, status, line, tuple(dict.fromkeys(cited)),
                             tuple(dict.fromkeys(flags))))
        # suppress older heads of the same subject signature
        newest_ts = {}
        for sig, ts, *_ in cand:
            newest_ts[sig] = max(newest_ts.get(sig, -1), ts)
        for sig, ts, oid, status, line, cited, flags in cand:
            if status == "current" and ts < newest_ts.get(sig, ts):
                status = "superseded"
                flags = tuple(f for f in flags if f != "conflict") + ("past_head",)
            out.append(Item(oid, _one_line(line), status, cited, flags, 1.0 / (len(out) + 1)))
        return out
