"""Traceability: C05."""
from __future__ import annotations

from ebrain.v3.contracts import FactState
from ebrain.v3.resolver.policy import DEFAULT_POLICY
from ebrain.v3.resolver.reducer import Resolver

from .test_resolver_v3 import claim, snap


def test_C05_bitemporal_cuts():
    old = claim("old", "old", seq=1, valid_from="2026-01-01T00:00:00+00:00")
    late = claim("late", "late", seq=5, valid_from="2026-01-15T00:00:00+00:00", base_seq=1)
    resolver = Resolver(DEFAULT_POLICY)
    known_before = resolver.resolve((old, late), (), (), (), snap(4, "2026-02-01T00:00:00+00:00"))
    known_after = resolver.resolve((old, late), (), (), (), snap(5, "2026-02-01T00:00:00+00:00"))
    assert [f.value for f in known_before if f.state is FactState.CURRENT] == ["old"]
    assert [f.value for f in known_after if f.state is FactState.CURRENT] == ["late"]
    future = resolver.resolve((late,), (), (), (), snap(5, "2026-01-02T00:00:00+00:00"))
    assert not [f for f in future if f.state is FactState.CURRENT]
