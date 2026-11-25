"""Traceability: M10."""
from __future__ import annotations

from ebrain.v3.contracts import SourceContract, Span
from ebrain.v3.sources.snapshots import SourceRegistry


def test_M10_idempotent_source_lifecycle():
    registry = SourceRegistry()
    revision = SourceRegistry.new_revision(
        source_id="repo", revision="r1", digest="d1", parser_version="v1",
        contract=SourceContract.FIRST_PARTY_DECLARED,
        spans=(Span(start=0, end=3, digest="s1"),),
    )
    assert registry.register(revision)
    assert not registry.register(revision)
    registry.rename("repo", "repo-renamed")
    assert registry.get("repo", "r1").source_id == "repo-renamed"
    registry.mark_partial("repo", "r1")
    assert registry.get("repo", "r1").partial_scan is True
    # A partial scan must not look like a retraction/deletion.
    assert registry.get("repo", "r1").retracted is False
    registry.retract("repo", "r1")
    assert registry.get("repo", "r1").retracted is True
