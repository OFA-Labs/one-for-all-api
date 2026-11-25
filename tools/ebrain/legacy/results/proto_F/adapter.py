"""Prototype F (EXPERIMENT ONLY): tunable anchor-lock assignment + original IDF
retrieval, with the external-supersedes (T3) fix restored.

Env knobs (for the parameter grid): AG1_RARE_CAP, AG1_COVERAGE_MIN,
AG1_RANK_MAX (overrides config rank_max_chains).
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store  # noqa: E402

RARE_CAP = int(os.environ.get("AG1_RARE_CAP", 12))
COVERAGE_MIN = float(os.environ.get("AG1_COVERAGE_MIN", 0.70))
AUTO_CAP = os.environ.get("AG1_RARE_CAP_MODE", "fixed") == "auto"
CAP_DIVISOR = int(os.environ.get("AG1_CAP_DIVISOR", 26))


class Adapter(Store):
    name = "proto-F-anchor-tuned"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")
        if os.environ.get("AG1_RANK_MAX"):
            self.cfg["rank_max_chains"] = int(os.environ["AG1_RANK_MAX"])

    def _rare_cap(self, p):
        """Scale-aware fixed point: grows with DISTINCT CHAINS, not memory count.
        At 1k/10k this stays at 12; at 50k it rises to ~48 so fact/scope tokens
        still qualify as anchors instead of all looking 'common'."""
        if not AUTO_CAP:
            return RARE_CAP
        n = self.db.execute("SELECT COUNT(DISTINCT chain) FROM terms WHERE user_id=? AND "
                            "project=?", (self.u, p)).fetchone()[0] or 0
        return max(12, min(64, n // CAP_DIVISOR))

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
        if targets:  # binding, external included (fixes hijack injection)
            return targets[0], None
        if not terms:
            return fallback, None
        df = {}
        if terms:
            q = ",".join("?" * len(terms))
            for r in db.execute(f"SELECT term, COUNT(DISTINCT chain) FROM terms WHERE user_id=? "
                                f"AND project=? AND term IN ({q}) GROUP BY term", (u, p, *terms)):
                df[r[0]] = r[1]
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        if not cands:
            return fallback, None
        vocab = self._chain_vocab(p, cands)
        core_all = set()
        for counts, nv in vocab.values():
            core_all |= self._core(counts, nv)
        if core_all:
            qq = ",".join("?" * len(core_all))
            for r in db.execute(f"SELECT term, COUNT(DISTINCT chain) FROM terms WHERE user_id=? "
                                f"AND project=? AND term IN ({qq}) GROUP BY term", (u, p, *core_all)):
                df[r[0]] = r[1]
        best, best_score = None, 0.0
        cap = self._rare_cap(p)
        for c, (counts, nv) in sorted(vocab.items()):
            core = self._core(counts, nv)
            anchors = {x for x in core if df.get(x, cap + 1) <= cap}
            if anchors - terms:
                continue
            coverage = len(terms & set(counts)) / len(terms)
            if coverage < COVERAGE_MIN:
                continue
            score = len(anchors) + coverage
            if score > best_score:
                best, best_score = c, score
        return best or fallback, None
