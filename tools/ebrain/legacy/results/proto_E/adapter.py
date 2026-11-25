"""Prototype E (EXPERIMENT ONLY): scale-invariant slot design.

Assignment: supersedes/path binding; otherwise 'anchor-lock' with a FIXED
rarity cap -- a write joins a chain only if it carries every distinctive core
(anchor) term and >= COVERAGE_MIN of its terms are known to that chain.

Retrieval: same invariant -- a chain is a candidate only if every anchor term
is present in the query; rank by anchor specificity + query coverage; keep
top-K. No corpus-size-dependent IDF drives any decision.
"""
import os
import sys

REF = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "FINAL", "reference", "impl")
sys.path.insert(0, REF)
from ebrain.store import Store, _one_line, _terms, CODE_RE, TOK_RE  # noqa: E402
from ebrain.models import Item, Bundle, count_tokens  # noqa: E402

RARE_CAP = int(os.environ.get("AG1_RARE_CAP", 12))
COVERAGE_MIN = float(os.environ.get("AG1_COVERAGE_MIN", 0.70))
TOPK = int(os.environ.get("AG1_TOPK", 8))


class Adapter(Store):
    name = "proto-E-slot-invariant"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")

    # ---------------- helpers ----------------
    def _df_for(self, p, terms, fallback_n):
        out = {}
        if not terms:
            return out
        q = ",".join("?" * len(terms))
        for r in self.db.execute(f"SELECT term, COUNT(DISTINCT chain) FROM terms "
                                 f"WHERE user_id=? AND project=? AND term IN ({q}) "
                                 f"GROUP BY term", (self.u, p, *terms)):
            out[r[0]] = r[1]
        return out

    def _anchors(self, p, cands, df):
        """chain -> (core, anchors, union_of_terms)."""
        vocab = self._chain_vocab(p, cands)
        info = {}
        core_all = set()
        for c, (counts, nv) in vocab.items():
            core = self._core(counts, nv)
            core_all |= core
            info[c] = [core, set(), set(counts)]
        extra = self._df_for(p, core_all, 0)
        for k, v in extra.items():
            df[k] = v
        for c, (core, _, union) in info.items():
            info[c][1] = {x for x in core if df.get(x, RARE_CAP + 1) <= RARE_CAP}
        return info

    # ---------------- assignment ----------------
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
        df = self._df_for(p, terms, 0)
        q = ",".join("?" * len(terms))
        cands = [r[0] for r in db.execute(f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND "
                                          f"project=? AND term IN ({q})", (u, p, *terms))]
        if not cands:
            return fallback, None
        info = self._anchors(p, cands, df)
        best, best_score = None, 0.0
        for c, (core, anchors, union) in sorted(info.items()):
            if anchors - terms:
                continue
            coverage = len(terms & union) / len(terms)
            if coverage < COVERAGE_MIN:
                continue
            score = len(anchors) + coverage
            if score > best_score:
                best, best_score = c, score
        return best or fallback, None

    # ---------------- retrieval ----------------
    def _rank(self, q, h):
        p, terms = q.project_id, _terms(q.text)
        if not terms:
            return []
        vis = "AND ts<=? AND (vis='shared' OR agent=?)"
        qm = ",".join("?" * len(terms))
        cands = [r[0] for r in self.db.execute(
            f"SELECT DISTINCT chain FROM terms WHERE user_id=? AND project=? AND term IN ({qm}) {vis}",
            (self.u, p, *terms, h, q.agent_id))]
        if not cands:
            return []
        df = self._df_for(p, terms, 0)
        info = self._anchors(p, cands, df)
        scored = []
        for c, (core, anchors, union) in info.items():
            if anchors - terms:
                continue
            coverage = len(terms & union) / len(terms)
            scored.append((-(len(anchors) + coverage), c))
        if not scored:
            return []
        scored.sort()
        return [c for s, c in scored[:TOPK]]
