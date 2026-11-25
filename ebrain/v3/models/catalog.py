"""Owner-approved local model candidate catalogue (D02/D07).

These are *candidates*, not active components. No artifact hashes have been
verified in this workspace, so every candidate is NOT_CONFIGURED and every
activation gate refuses to open. The resolver remains model-free regardless.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

from .manifest import ModelManifest


@dataclass(frozen=True)
class Candidate:
    role: str
    model_id: str
    dimensions: int
    preprocessing: str
    metric: str
    language: str
    approved_use: str
    artifact_digest: str = ""
    runtime_digest: str = ""
    calibration_digest: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.artifact_digest and self.runtime_digest and self.calibration_digest)

    def manifest(self) -> ModelManifest | None:
        """Refuse to build a usable manifest until hashes are verified."""
        if not self.configured:
            return None
        return ModelManifest(
            manifest_id=f"{self.role}:{self.model_id}",
            artifact_digest=self.artifact_digest,
            tokenizer_digest=self.artifact_digest,
            runtime=self.runtime_digest,
            preprocess_digest=self.preprocessing,
            schema_version="3",
            calibration_digest=self.calibration_digest,
            dimensions=self.dimensions,
            space_id=f"{self.role}:{self.model_id}:{self.artifact_digest[:8]}",
            egress_enabled=False,
        )


CATALOGUE: Final[Mapping[str, Candidate]] = {
    c.role: c for c in (
        Candidate(
            "embedding_primary", "intfloat/multilingual-e5-small", 384,
            "query: / passage: prefixes pinned", "cosine", "en/hi/hinglish",
            "scoped vector candidates only",
        ),
        Candidate(
            "embedding_comparison", "BAAI/bge-small-en-v1.5", 384,
            "English comparator, pinned preprocessing", "cosine", "en",
            "comparison only; never mixed into the primary space",
        ),
        Candidate(
            "reranker", "cross-encoder/ms-marco-MiniLM-L6-v2", 0,
            "pinned query/passage schema", "score", "en",
            "candidate reranking; cannot remove protected facts",
        ),
        Candidate(
            "classifier", "typed-rules-first", 0,
            "strict typed output schema", "n/a", "en/hi/hinglish",
            "async filing suggestions only; never an applied binding",
        ),
        Candidate(
            "optional_llm", "qwen3:4b (local Ollama)", 0,
            "grounded JSON schema", "n/a", "en/hi/hinglish",
            "hard-case suggestions and grounded summaries; not authoritative",
        ),
    )
}


def activation_gate(role: str, *, offline_proof: bool, calibrated: bool) -> bool:
    """A candidate activates only with verified hashes, offline proof and calibration."""
    candidate = CATALOGUE[role]
    return candidate.configured and offline_proof and calibrated and candidate.manifest() is not None


def catalogue_status() -> dict[str, str]:
    return {role: "CONFIGURED" if c.configured else "NOT_CONFIGURED"
            for role, c in CATALOGUE.items()}
