"""Shadow rebuild and independent audit (CP12.2/C08)."""
from __future__ import annotations

from dataclasses import dataclass

from .materialize import Card, card_digest


@dataclass(frozen=True)
class RebuildReport:
    match: bool
    authoritative_digest: str
    shadow_digest: str
    differences: tuple[str, ...]
    independent_issues: tuple[str, ...]

    @property
    def safe_to_activate(self) -> bool:
        return self.match and not self.independent_issues


def reconcile(
    authoritative: tuple[Card, ...], shadow: tuple[Card, ...]
) -> tuple[str, ...]:
    a = {c.fact_id: c.digest() for c in authoritative}
    s = {c.fact_id: c.digest() for c in shadow}
    issues: list[str] = []
    for fact_id in sorted(set(a) | set(s)):
        if a.get(fact_id) != s.get(fact_id):
            issues.append(f"card_mismatch:{fact_id}")
    return tuple(issues)


def independent_identity_audit(
    cards: tuple[Card, ...], bindings: dict[str, str]
) -> tuple[str, ...]:
    """Reference replay: a card may never invent or promote a fact binding."""
    issues: list[str] = []
    for card in cards:
        if card.derivation != "resolver":
            issues.append(f"non_authoritative_derivation:{card.fact_id}")
        expected = bindings.get(card.fact_id)
        if expected is not None and expected != card.fact_id:
            issues.append(f"false_binding:{card.fact_id}")
        if card.state == "current" and not card.source_digests:
            issues.append(f"current_without_evidence:{card.fact_id}")
    return tuple(issues)


def rebuild_report(
    authoritative: tuple[Card, ...], shadow: tuple[Card, ...],
    bindings: dict[str, str],
) -> RebuildReport:
    diff = reconcile(authoritative, shadow)
    audit = independent_identity_audit(shadow, bindings)
    return RebuildReport(
        match=not diff,
        authoritative_digest=card_digest(authoritative),
        shadow_digest=card_digest(shadow),
        differences=diff,
        independent_issues=audit,
    )
