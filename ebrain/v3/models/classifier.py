"""Strict, optional filing classifier boundary.

No model, network or paid provider is invoked here. A disabled classifier always
returns ``unavailable`` so eligible fences stay until reviewed. Any injected
classifier is untrusted and its output is validated against known candidates and
a strict schema before it can become a *proposal* — never an applied binding.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from ..contracts import Candidate, digest_of
from ..errors import SemanticReject
from .manifest import ModelManifest


class Suggestion(BaseModel):
    """Strict schema for a classifier suggestion; extra fields are rejected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    candidate_fact_id: str | None = None
    new_key: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    near_miss: bool = False
    missing_qualifier: str = ""
    reason: str = ""


@dataclass(frozen=True)
class SuggestionResult:
    available: bool
    suggestion: Suggestion | None = None
    manifest_digest: str = ""
    reason: str = ""


class FilingClassifier(Protocol):
    manifest: ModelManifest

    def suggest(self, sanitized_text: str, candidates: tuple[Candidate, ...]) -> SuggestionResult: ...


@dataclass(frozen=True)
class DisabledClassifier:
    """Default: no model. Deterministic and dependency-free."""

    manifest: ModelManifest | None = None

    def suggest(self, sanitized_text: str, candidates: tuple[Candidate, ...]) -> SuggestionResult:
        return SuggestionResult(False, None, "", "classifier disabled")


def validate_suggestion(
    result: SuggestionResult, candidates: tuple[Candidate, ...]
) -> Suggestion | None:
    """An unavailable/invalid classifier result leaves the claim pending."""
    if not result.available or result.suggestion is None:
        return None
    suggestion = result.suggestion
    if suggestion.candidate_fact_id:
        allowed = {c.fact_id for c in candidates}
        if suggestion.candidate_fact_id not in allowed:
            raise SemanticReject("classifier referenced an unknown candidate")
        if suggestion.near_miss:
            raise SemanticReject("near-miss classifier output cannot bind a fact")
    if not suggestion.candidate_fact_id and not suggestion.new_key:
        raise SemanticReject("classifier produced no actionable strict output")
    return suggestion


def suggestion_digest(text: str, candidates: tuple[Candidate, ...]) -> str:
    """Cache key by sanitized input/scope, never by labels."""
    return digest_of({
        "text": text,
        "candidates": [{"fact_id": c.fact_id, "scope": c.key.scope} for c in candidates],
    })
