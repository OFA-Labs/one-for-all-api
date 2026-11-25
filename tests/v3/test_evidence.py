"""Traceability: M06."""
from __future__ import annotations

from ebrain.v3.contracts import Claim, ClaimKind, SourceContract, SourceRevision, Span
from ebrain.v3.projections.evidence import verify_evidence
from ebrain.v3.sources.snapshots import SourceRegistry

from .v3_helpers import key


def test_M06_exact_sanitized_revision():
    span = Span(start=2, end=8, digest="span-1", label="value")
    revision = SourceRegistry.new_revision(
        source_id="repo", revision="r1", digest="rev-1", parser_version="v1",
        contract=SourceContract.APPROVED_ARTIFACT, spans=(span,),
    )
    registry = SourceRegistry()
    assert registry.register(revision) is True
    assert registry.register(revision) is False
    claim = Claim(
        claim_id="c", key=key(), kind=ClaimKind.ASSERTION, value="value", unit=None,
        source=revision, principal_id="alice", valid_from="2026-01-01T00:00:00+00:00",
        knowledge_seq=1, digest="d", fact_id=key().key_id,
    )
    assert verify_evidence(claim, registry).span == span
    registry.retract("repo", "r1")
    assert not verify_evidence(claim, registry).verified
