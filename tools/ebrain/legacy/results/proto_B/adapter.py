"""Prototype B (EXPERIMENT ONLY): scale-invariant 'anchor-lock' chain assignment.

Instead of IDF-mass scoring whose threshold drifts with corpus size, a write
joins a candidate chain only when:
  1. it carries every distinctive ('anchor') core term of that chain, and
  2. >= 70% of its own terms are already known to that chain.
Rarity is decided with a FIXED cap (independent of corpus size), so 10k/50k
behave like 1k. supersedes and path remain binding first.
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store  # noqa: E402

RARE_CAP = 12       # fixed: a term in <=12 chains is 'distinctive' at any size
COVERAGE_MIN = 0.70  # fraction of write terms that must be known to the chain


class Adapter(Store):
    name = "proto-B-anchor-lock"

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
        if targets and not ext:
            return targets[0], None
        if not terms:
            return fallback, None
        # fixed-rarity document frequency for only the terms we care about
        _, df, n = self._idf(p, terms)
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        if not cands:
            return fallback, None
        vocab = self._chain_vocab(p, cands)
        # look up df for candidate core terms too
        core_terms = set()
        for counts, nv in vocab.values():
            core_terms |= self._core(counts, nv)
        if core_terms:
            qq = ",".join("?" * len(core_terms))
            for r in db.execute(f"SELECT term, COUNT(DISTINCT chain) FROM terms WHERE user_id=? "
                                f"AND project=? AND term IN ({qq}) GROUP BY term",
                                (u, p, *core_terms)):
                df[r[0]] = r[1]
        best, best_score = None, 0.0
        for c in sorted(vocab):
            counts, nv = vocab[c]
            core = self._core(counts, nv)
            anchors = {x for x in core if df.get(x, n + 1) <= RARE_CAP}
            if anchors - terms:
                continue  # chain has a distinctive term this write lacks -> different fact
            known = set(counts)
            coverage = len(terms & known) / len(terms)
            if coverage < COVERAGE_MIN:
                continue
            # prefer the most specific (largest anchor set), then coverage
            score = len(anchors) + coverage
            if score > best_score:
                best, best_score = c, score
        if best:
            return best, None
        return fallback, None
