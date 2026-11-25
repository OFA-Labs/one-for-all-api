"""Prototype C (EXPERIMENT ONLY): original v2 assignment with two surgical fixes.

1. supersedes is binding (external included) -- never let a fuzzy match override
   an explicit writer signal or a T3 poison target.
2. 'clash' veto uses a FIXED rarity cap (6 chains) instead of max(2, n//8),
   which grows to 31 at 10k and 156 at 50k and stops separating near-miss facts.
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store  # noqa: E402

RARE_CAP = 6


class Adapter(Store):
    name = "proto-C-fixed-clash"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")

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
        # FIX 1: supersedes binding, external included
        if targets:
            return targets[0], None
        idf, df, n = self._idf(p, terms)
        rare = {t for t in terms if df[t] <= RARE_CAP}
        if not terms:
            return fallback, None
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        vocab = self._chain_vocab(p, cands) if cands else {}
        best, best_s, scored = None, 0.0, []
        tot = sum(idf.values()) or 1.0
        for c in sorted(vocab):
            counts, nv = vocab[c]
            core = self._core(counts, nv)
            a = sum(idf[t] for t in terms if t in counts) / tot
            core_idf = {x: __import__("math").log(1 + (n + 1) / (1 + df.get(x, 1))) for x in core}
            b = sum(v for x, v in core_idf.items() if x in terms) / (sum(core_idf.values()) or 1)
            s = (a * b) ** 0.5
            # FIX 2: fixed rarity cap for the clash veto
            missing_rare = {x for x in core - terms if df.get(x, n + 1) <= RARE_CAP}
            clash = bool((rare - set(counts)) and missing_rare)
            scored.append((c, s, core, clash))
            if not clash and s > best_s:
                best, best_s = c, s
        thr = self.cfg["slot_match_threshold_external" if ext else "slot_match_threshold"]
        if best and best_s >= thr:
            return best, None
        return fallback, None
