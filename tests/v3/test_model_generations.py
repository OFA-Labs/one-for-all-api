"""Traceability: H03."""
from __future__ import annotations

import pytest

from ebrain.v3.config import V3Config
from ebrain.v3.contracts import Selector
from ebrain.v3.models.manifest import ModelManifest

from .test_pipeline_v3 import service
from .v3_helpers import SCOPE, ctx


def test_H03_incompatible_space_cutover():
    a = ModelManifest("m1", "a", "t", "runtime", "p", "1", "c", 8, "space-A")
    b = ModelManifest("m2", "b", "t", "runtime", "p", "1", "c", 8, "space-B")
    assert not a.compatible_with(b)
    svc = service(V3Config(vector_retrieval_enabled=True))
    c = ctx()
    result = svc.retriever.candidates(
        c, Selector(scope=SCOPE),
        svc.ledger.snapshot(c), svc.ledger.load_slice(c, (), svc.ledger.seq),
    )
    assert "vector_unavailable" in result.degradation


def test_D02_D07_candidates_are_pinned_but_inactive():
    from ebrain.v3.models.catalog import CATALOGUE, activation_gate, catalogue_status

    assert CATALOGUE["embedding_primary"].dimensions == 384
    assert CATALOGUE["embedding_comparison"].dimensions == 384
    assert CATALOGUE["reranker"].model_id == "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert all(v == "NOT_CONFIGURED" for v in catalogue_status().values())
    assert not activation_gate("embedding_primary", offline_proof=True, calibrated=True)
    assert CATALOGUE["embedding_primary"].manifest() is None
