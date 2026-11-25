"""Traceability: M05. Typed contradiction first; NLI advisory only."""
from __future__ import annotations

from ebrain.v3.config import V3Config
from ebrain.v3.projections.derived import DerivedDAG

from ..test_resolver_v3 import claim
from ..v3_helpers import key


def typed_contradiction(a, b) -> bool:
    same_fact = a.fact_id == b.fact_id
    overlapping = a.valid_from is not None and b.valid_from is not None
    incompatible = a.value != b.value
    return same_fact and overlapping and incompatible


def test_M05_typed_first_advisory_nli(pg_ledger):
    a = claim("a", "v1", seq=1)
    b = claim("b", "v2", seq=2, base_seq=1)
    assert typed_contradiction(a, b)
    # Maintenance cannot change current: only a reviewed decision can.
    assert V3Config().nli_maintenance_enabled is False
    assert DerivedDAG().artifacts == {}
