"""Incremental, advisory consolidation/lint jobs (M12 CP12.3 / M05).

Typed contradiction detection comes first. NLI is advisory only and disabled by
default. Issues are deduplicated by target+rule+evidence revision and can never
mutate authoritative current state.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import V3Config
from ..contracts import Claim, digest_of
from .outbox import Outbox, OutboxJob


@dataclass(frozen=True)
class Issue:
    issue_id: str
    target: str
    rule: str
    evidence_revision: str
    advisory: bool = True

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        return (self.target, self.rule, self.evidence_revision)


@dataclass
class ConsolidationService:
    cfg: V3Config
    outbox: Outbox = field(default_factory=lambda: Outbox(V3Config()))
    issues: dict[tuple[str, str, str], Issue] = field(default_factory=dict)

    def typed_contradictions(self, claims: tuple[Claim, ...]) -> tuple[Issue, ...]:
        found: list[Issue] = []
        ordered = tuple(sorted(claims, key=lambda c: (c.fact_id or "", c.knowledge_seq)))
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                if left.fact_id is None or left.fact_id != right.fact_id:
                    continue
                if left.valid_from is None or right.valid_from is None:
                    continue
                if left.valid_to and right.valid_from >= left.valid_to:
                    continue
                if left.value == right.value:
                    continue
                revision = digest_of({
                    "left": left.digest, "right": right.digest,
                })
                found.append(Issue(
                    issue_id="iss_" + digest_of({
                        "target": left.fact_id, "rule": "typed_contradiction",
                        "revision": revision,
                    })[:20],
                    target=left.fact_id, rule="typed_contradiction",
                    evidence_revision=revision,
                ))
        return tuple(found)

    def lint(self, claims: tuple[Claim, ...], pending_unbound: int = 0) -> tuple[Issue, ...]:
        found: list[Issue] = []
        for claim in claims:
            if not claim.source.digest:
                found.append(Issue(
                    issue_id="iss_lint_" + claim.claim_id[:12], target=claim.claim_id,
                    rule="missing_source_digest", evidence_revision=claim.digest,
                ))
            if claim.fact_id is None:
                found.append(Issue(
                    issue_id="iss_unbound_" + claim.claim_id[:12], target=claim.claim_id,
                    rule="unbound_claim", evidence_revision=claim.digest,
                ))
        if pending_unbound and not found:
            found.append(Issue(
                issue_id="iss_pending_debt", target="unassigned",
                rule="pending_debt", evidence_revision=str(pending_unbound),
            ))
        return tuple(found)

    def record(self, issues: tuple[Issue, ...]) -> int:
        """Idempotent by target+rule+evidence revision. No authoritative change."""
        added = 0
        for issue in issues:
            if issue.dedup_key in self.issues:
                continue
            self.issues[issue.dedup_key] = issue
            self.outbox.enqueue(OutboxJob(
                job_id=f"lint:{issue.issue_id}", job_type="advisory",
                scope="maintenance", payload_digest=issue.issue_id,
                knowledge_seq=0,
            ))
            added += 1
        return added

    @property
    def advisory_only(self) -> bool:
        return all(issue.advisory for issue in self.issues.values())
