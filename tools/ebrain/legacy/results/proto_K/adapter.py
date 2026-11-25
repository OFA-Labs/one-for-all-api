"""Prototype K (EXPERIMENT ONLY): anchor-boosted retrieval.

Keeps proto_F assignment and the IDF retrieval as the candidate generator, but
reranks the shortlist so chains whose anchor words are all present in the query
come first. Unlike proto_E this never REJECTS a chain, so alias rewordings still
work; it only prioritises exact subject matches.
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PF = os.path.join(os.path.dirname(HERE), "proto_F")
spec = importlib.util.spec_from_file_location("proto_f_base", os.path.join(PF, "adapter.py"))
mod = importlib.util.module_from_spec(spec)
sys.modules["proto_f_base"] = mod
spec.loader.exec_module(mod)
Base = mod.Adapter

from ebrain.store import _terms  # noqa: E402


class Adapter(Base):
    name = "proto-K-anchor-boost"

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
        core_all, data = set(), {}
        for c, (counts, nv) in vocab.items():
            core = self._core(counts, nv)
            core_all |= core
            data[c] = core
        for k, v in self._df_for(p, core_all).items():
            df[k] = v
        cap = self._rare_cap(p)
        return {c: frozenset(x for x in core if df.get(x, cap + 1) <= cap)
                for c, core in data.items()}

    def _rank(self, q, h):
        old = self.cfg.get("rank_max_chains", 8)
        self.cfg["rank_max_chains"] = 32
        cands = list(super()._rank(q, h))
        self.cfg["rank_max_chains"] = old
        if not cands:
            return []
        terms = _terms(q.text)
        amap = self._anchor_map(q.project_id, cands, self._df_for(q.project_id, terms))
        order = {c: i for i, c in enumerate(cands)}

        def key(c):
            anchors = amap.get(c, frozenset())
            return (0 if anchors and anchors <= terms else 1, order[c])

        cands.sort(key=key)
        return cands[:old]
