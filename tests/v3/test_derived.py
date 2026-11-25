"""Traceability: H04."""
from __future__ import annotations

import pytest

from ebrain.v3.contracts import ClaimKind, SourceContract
from ebrain.v3.projections.derived import DerivedArtifact, DerivedDAG


def test_H04_no_recursive_authority():
    dag = DerivedDAG(max_depth=2)
    dag.add(DerivedArtifact("d1", ("fact1",), 1, "manifest"))
    dag.add(DerivedArtifact("d2", ("d1",), 2, "manifest"))
    assert dag.descendants("fact1") == ("d1", "d2")
    with pytest.raises(ValueError):
        dag.add(DerivedArtifact("d3", ("d1", "d2"), 3, "manifest", depth=3))
    for payload in dag.as_noncurrent_claims("scope", "resource"):
        assert payload["kind"] == ClaimKind.DERIVED.value
        assert payload["source_contract"] == SourceContract.DERIVED.value
