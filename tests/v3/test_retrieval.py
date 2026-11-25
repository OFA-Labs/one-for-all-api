"""Traceability: H01."""
from __future__ import annotations

from ebrain.v3.contracts import Selector
from ebrain.v3.retrieval.query import fuse

from .test_pipeline_v3 import seeded_service
from .v3_helpers import SCOPE, ctx


def test_H01_protected_multifacet_candidates():
    svc = seeded_service()
    c = ctx()
    selector = Selector(scope=SCOPE, predicate="decision.status", resource_id="svc",
                        qualifiers=(("repo", "acme/api"), ("environment", "prod")), text="svc")
    result = svc.retriever.candidates(c, selector, svc.ledger.snapshot(c),
                                      svc.ledger.load_slice(c, (), svc.ledger.seq))
    protected = [x for x in result.candidates if x.protected]
    assert protected
    fused = fuse({"exact": tuple(protected), "lexical": (), "vector": ()})
    assert any(x.fact_id == protected[0].fact_id and x.protected for x in fused)
    assert result.complete
