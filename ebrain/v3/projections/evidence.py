"""Exact sanitized evidence checks (M06 / CP12.4)."""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import Claim, Provenance, Span
from ..errors import SemanticReject
from ..sources.snapshots import SourceRegistry


@dataclass(frozen=True)
class EvidenceReport:
    verified: bool
    reason: str
    span: Span | None = None


def verify_evidence(
    claim: Claim, registry: SourceRegistry, span: Span | None = None
) -> EvidenceReport:
    """A string occurrence or a model's self-judgement is not proof."""
    revision = registry.get(claim.source.source_id, claim.source.revision)
    if revision is None:
        return EvidenceReport(False, "source_revision_missing")
    if revision.retracted or revision.partial_scan:
        return EvidenceReport(False, "source_revision_not_eligible")
    if revision.digest != claim.source.digest:
        return EvidenceReport(False, "digest_mismatch")
    if span is None:
        if claim.source.spans:
            span = claim.source.spans[0]
        else:
            return EvidenceReport(False, "no_exact_span")
    if not registry.span_digest(claim.source.source_id, claim.source.revision, span):
        return EvidenceReport(False, "span_not_verified")
    if span.end <= span.start:
        raise SemanticReject("invalid span offsets")
    return EvidenceReport(True, "verified", span)


def to_provenance(claim: Claim, report: EvidenceReport, freshness_value: str = "unknown") -> Provenance:
    return Provenance(
        source_id=claim.source.source_id,
        revision=claim.source_revision,
        digest=claim.source.digest,
        span=report.span,
        freshness=freshness_value,
        contract=claim.source.contract,
    )
