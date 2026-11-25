"""Prototype H (EXPERIMENT ONLY): anchor-lock first, legacy IDF fallback.

Where anchor-lock finds no chain, the shipped v2 IDF matcher is used instead of
creating a fresh chain. Goal: keep the accuracy gain of separation while
cutting the fragmentation-driven zombie regression.
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store  # noqa: E402
import math

RARE_CAP = int(os.environ.get("AG1_RARE_CAP", 12))
COVERAGE_MIN = float(os.environ.get("AG1_COVERAGE_MIN", 0.85))


class Adapter(Store):
    name = "proto-H-slot-then-legacy"

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
        df = self._df_for(p, terms)
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        if not cands:
            return fallback, None
        vocab = self._chain_vocab(p, cands)
        core_all = set()
        for counts, nv in vocab.values():
            core_all |= self._core(counts, nv)
        for k, v in self._df_for(p, core_all).items():
            df[k] = v

        # 1) anchor-lock
        best, best_score = None, 0.0
        for c, (counts, nv) in sorted(vocab.items()):
            core = self._core(counts, nv)
            anchors = {x for x in core if df.get(x, RARE_CAP + 1) <= RARE_CAP}
            if anchors - terms:
                continue
            coverage = len(terms & set(counts)) / len(terms)
            if coverage < COVERAGE_MIN:
                continue
            score = len(anchors) + coverage
            if score > best_score:
                best, best_score = c, score
        if best:
            return best, None

        # 2) legacy IDF fallback (scale-dependent) -- avoid fresh-chain fragmentation
        idf, df2, n = self._idf(p, terms)
        rare = {t for t in terms if df2[t] <= max(2, n // 8)}
        best2, best_s = None, 0.0
        tot = sum(idf.values()) or 1.0
        for c, (counts, nv) in vocab.items():
            core = self._core(counts, nv)
            a = sum(idf[t] for t in terms if t in counts) / tot
            cidf = {x: math.log(1 + (n + 1) / (1 + df2.get(x, 1))) for x in core}
            b = sum(v for x, v in cidf.items() if x in terms) / (sum(cidf.values()) or 1)
            s = (a * b) ** 0.5
            missing = {x for x in core - terms if df2.get(x, n + 1) <= max(2, n // 8)}
            clash = bool((rare - set(counts)) and missing)
            if not clash and s > best_s:
                best2, best_s = c, s
        thr = self.cfg["slot_match_threshold_external" if ext else "slot_match_threshold"]
        if best2 and best_s >= thr:
            return best2, None
        return fallback, None
