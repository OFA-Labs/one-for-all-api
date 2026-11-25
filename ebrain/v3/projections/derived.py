"""Derived artifact DAG (H04 / CP12.4). Never independent current evidence."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import ClaimKind, SourceContract, digest_of


@dataclass(frozen=True)
class DerivedArtifact:
    artifact_id: str
    dependencies: tuple[str, ...]
    creation_seq: int
    manifest_digest: str
    depth: int = 1
    adopted_by_decision: str = ""

    @property
    def can_be_current_evidence(self) -> bool:
        return False


@dataclass
class DerivedDAG:
    artifacts: dict[str, DerivedArtifact] = field(default_factory=dict)
    max_depth: int = 4

    def add(self, artifact: DerivedArtifact) -> None:
        if artifact.artifact_id in self.artifacts:
            return
        if artifact.depth > self.max_depth:
            raise ValueError("derived depth limit exceeded")
        if any(dep == artifact.artifact_id for dep in artifact.dependencies):
            raise ValueError("derived cycle rejected")
        self.artifacts[artifact.artifact_id] = artifact

    def dependents(self, artifact_id: str) -> tuple[str, ...]:
        """Retraction/erasure propagates unsupported/pending to dependents."""
        out = [aid for aid, a in self.artifacts.items() if artifact_id in a.dependencies]
        return tuple(sorted(out))

    def descendants(self, artifact_id: str) -> tuple[str, ...]:
        seen: set[str] = set()
        frontier = [artifact_id]
        while frontier:
            for dep in self.dependents(frontier.pop()):
                if dep not in seen:
                    seen.add(dep)
                    frontier.append(dep)
        return tuple(sorted(seen))

    def as_noncurrent_claims(self, scope: str, resource_id: str) -> tuple[dict[str, object], ...]:
        """Derived artifacts are evidence-only; they never become primary claims."""
        return tuple(
            {
                "kind": ClaimKind.DERIVED.value,
                "source_contract": SourceContract.DERIVED.value,
                "value": digest_of({"artifact": aid}),
                "scope": scope,
                "resource_id": resource_id,
            }
            for aid in sorted(self.artifacts)
        )
