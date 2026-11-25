"""Traceability: H02."""
from __future__ import annotations

from ebrain.v3.config import V3Config
from ebrain.v3.contracts import Candidate, SourceContract, WriteRequest
from ebrain.v3.identity.filing import FilingService
from ebrain.v3.identity.keys import canonical_key
from ebrain.v3.identity.ledger import IdentityLedger

from .v3_helpers import ORG, SCOPE, key


def test_H02_calibrated_pending_hard_negative():
    """Near-miss text and unknown qualifiers stay pending; no destructive auto-merge."""
    ident = IdentityLedger()
    service = FilingService(ident, V3Config(semantic_filing_enabled=True))
    near = WriteRequest(
        op_id="near", key=key(), text="almost the same service but staging",
        source_id="git", source_revision="r", idempotency_key="near",
    )
    result = service.file(near, candidates=(
        Candidate(fact_id="other", key=key(resource_id="other"), arm="vector", rank=1,
                  score=0.99),
    ))
    assert result.outcome == "pending"
    assert result.fact_id is None
    external = WriteRequest(
        op_id="ext", key=key(), text="external claim", idempotency_key="ext",
        source_contract=SourceContract.EXTERNAL_OBSERVATION,
    )
    assert service.file(external).outcome == "noncurrent"
