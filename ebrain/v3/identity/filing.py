"""Deterministic filing first; model output is proposal-only (M9 CP9.4/9.5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..config import V3Config
from ..contracts import Candidate, ClaimKind, FactKey, SourceContract, WriteRequest, digest_of
from ..errors import AmbiguousIdentity, SemanticReject
from ..models.classifier import (
    DisabledClassifier,
    FilingClassifier,
    validate_suggestion,
)
from .keys import PREDICATES
from .ledger import IdentityLedger

Outcome = Literal["exact", "alias", "pending", "noncurrent", "proposal"]


@dataclass(frozen=True)
class FilingResult:
    outcome: Outcome
    key: FactKey | None
    fact_id: str | None
    reason: str
    proposal_digest: str = ""


@dataclass
class FilingService:
    identity: IdentityLedger
    cfg: V3Config
    classifier: FilingClassifier | None = None

    def file(
        self,
        request: WriteRequest,
        candidates: tuple[Candidate, ...] = (),
        *,
        seq: int | None = None,
    ) -> FilingResult:
        """Authorized structured id -> approved exact alias -> pending.

        Similarity never overrides an exact key. A model suggestion can only
        create a reviewable proposal and can never bind existing facts itself.
        """
        if request.source_contract in (SourceContract.EXTERNAL_OBSERVATION, SourceContract.DERIVED):
            return FilingResult("noncurrent", request.key, None, "evidence only; not current")
        if request.key is None:
            return FilingResult("pending", None, None, "no structured key")
        spec = PREDICATES.get(request.key.predicate)
        if spec is None:
            raise SemanticReject("predicate is not registered")
        fact_id = self.identity.fact_for_key(request.key, seq)
        if fact_id is not None:
            return FilingResult("exact", request.key, fact_id, "approved exact key")
        alias_id = self.identity.alias_fact(request.key.scope, request.key.resource_id)
        if alias_id is not None:
            return FilingResult("alias", request.key, alias_id, "approved scoped alias")
        if self.cfg.semantic_filing_enabled and self.classifier is not None:
            result = self.classifier.suggest(request.text, candidates)
            suggestion = validate_suggestion(result, candidates)
            if suggestion is not None:
                if suggestion.candidate_fact_id:
                    # A model-only equivalence is a proposal, not a binding.
                    return FilingResult(
                        "proposal", request.key, None,
                        "model suggestion requires review",
                        digest_of({"proposal": suggestion.model_dump(), "seq": seq}),
                    )
                if suggestion.missing_qualifier:
                    return FilingResult("pending", request.key, None,
                                        f"missing qualifier: {suggestion.missing_qualifier}")
        return FilingResult("pending", request.key, None, "unassigned exact key")


__all__ = ["FilingService", "FilingResult", "DisabledClassifier"]
