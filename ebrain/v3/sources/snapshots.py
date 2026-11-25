"""Source revision lifecycle: dedup, rename, retraction, partial scans, spans."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import SourceContract, SourceRevision, Span, digest_of
from ..errors import SemanticReject


@dataclass
class SourceRegistry:
    revisions: dict[tuple[str, str], SourceRevision] = field(default_factory=dict)
    renames: dict[str, str] = field(default_factory=dict)       # old -> canonical id
    retractions: set[tuple[str, str]] = field(default_factory=set)
    partial_scans: set[tuple[str, str]] = field(default_factory=set)

    @staticmethod
    def new_revision(
        *,
        source_id: str,
        revision: str,
        digest: str,
        parser_version: str,
        contract: SourceContract,
        spans: tuple[Span, ...] = (),
        acl_lineage: tuple[str, ...] = (),
    ) -> SourceRevision:
        return SourceRevision(
            source_id=source_id, revision=revision, digest=digest,
            parser_version=parser_version, contract=contract,
            spans=spans, acl_lineage=acl_lineage,
        )

    def register(self, revision: SourceRevision) -> bool:
        """Idempotent scoped revision dedup. Returns True when newly registered."""
        key = (revision.source_id, revision.revision)
        if key in self.revisions:
            existing = self.revisions[key]
            if existing.digest != revision.digest:
                raise SemanticReject("source revision digest changed")
            return False
        self.revisions[key] = revision
        return True

    def rename(self, old_id: str, new_id: str) -> None:
        """Rename retains resource identity; old scoped aliases keep resolving."""
        self.renames[old_id] = new_id

    def canonical_id(self, source_id: str) -> str:
        seen: set[str] = set()
        current = source_id
        while current in self.renames:
            if current in seen:
                raise SemanticReject("source rename cycle")
            seen.add(current)
            current = self.renames[current]
        return current

    def mark_partial(self, source_id: str, revision: str) -> None:
        """Permission failure/partial scan never means the source was deleted."""
        self.partial_scans.add((self.canonical_id(source_id), revision))

    def retract(self, source_id: str, revision: str) -> None:
        self.retractions.add((self.canonical_id(source_id), revision))

    def get(self, source_id: str, revision: str) -> SourceRevision | None:
        canonical = self.canonical_id(source_id)
        rev = self.revisions.get((canonical, revision)) or self.revisions.get((source_id, revision))
        if rev is None:
            return None
        return rev.model_copy(update={
            "source_id": canonical,
            "retracted": (canonical, revision) in self.retractions,
            "partial_scan": (canonical, revision) in self.partial_scans,
            "acl_lineage": rev.acl_lineage,
        })

    def span_digest(self, source_id: str, revision: str, span: Span) -> bool:
        """Verify a sanitized span digest against the immutable revision."""
        rev = self.get(source_id, revision)
        if rev is None:
            return False
        return any(s.digest == span.digest and s.start == span.start and s.end == span.end
                   for s in rev.spans)

    @staticmethod
    def evidence_digest(payload: object) -> str:
        return digest_of({"evidence": payload})
