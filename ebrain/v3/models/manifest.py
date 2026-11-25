"""Immutable model/index artifact manifest. No provider/network selection here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import digest_of
from ..errors import IncompatibleGeneration


@dataclass(frozen=True)
class ModelManifest:
    manifest_id: str
    artifact_digest: str
    tokenizer_digest: str
    runtime: str
    preprocess_digest: str
    schema_version: str
    calibration_digest: str
    dimensions: int = 0
    space_id: str = ""
    egress_enabled: bool = False

    def __post_init__(self) -> None:
        if self.egress_enabled:
            raise IncompatibleGeneration("model egress is not permitted in V3")
        if not all((self.artifact_digest, self.tokenizer_digest, self.runtime,
                    self.preprocess_digest, self.schema_version)):
            raise IncompatibleGeneration("manifest is incomplete")

    def digest(self) -> str:
        return digest_of({"manifest": self.as_dict()})

    def as_dict(self) -> Mapping[str, object]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}  # type: ignore[attr-defined]

    def compatible_with(self, other: ModelManifest) -> bool:
        return (
            self.manifest_id == other.manifest_id
            and self.space_id == other.space_id
            and self.dimensions == other.dimensions
            and self.artifact_digest == other.artifact_digest
        )
