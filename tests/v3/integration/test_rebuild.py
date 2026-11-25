"""Traceability: C08."""
from __future__ import annotations

from dataclasses import replace

from ebrain.v3.contracts import Snapshot
from ebrain.v3.projections.materialize import Card, materialize
from ebrain.v3.projections.rebuild import rebuild_report


def test_C08_independent_identity_audit(pg_ledger, pg_conn):
    cards = (Card("f1", "k", "current", "v", ("c1",), ("s1",), (1, 1, 1)),)
    report = rebuild_report(cards, cards, {})
    assert report.safe_to_activate
    poisoned = (replace(cards[0], derivation="model"),)
    bad = rebuild_report(cards, poisoned, {})
    assert not bad.safe_to_activate
    assert bad.independent_issues
