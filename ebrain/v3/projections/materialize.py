"""Deterministic card materializer from approved resolver output only (CP12.1)."""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import Claim, Snapshot, digest_of
from ..resolver.types import ResolvedFact


@dataclass(frozen=True)
class Card:
    fact_id: str
    key_digest: str
    state: str
    value_digest: str
    claim_ids: tuple[str, ...]
    source_digests: tuple[str, ...]
    watermarks: tuple[int, int, int]  # ledger, identity, policy
    derivation: str = "resolver"

    def digest(self) -> str:
        return digest_of({
            "fact_id": self.fact_id, "key_digest": self.key_digest,
            "state": self.state, "value_digest": self.value_digest,
            "claim_ids": list(self.claim_ids),
            "source_digests": list(self.source_digests),
            "watermarks": list(self.watermarks),
            "derivation": self.derivation,
        })


def materialize(
    facts: tuple[ResolvedFact, ...], claims: tuple[Claim, ...], snapshot: Snapshot
) -> tuple[Card, ...]:
    """Every field is ledger/identity/policy derived; generated prose is separate."""
    by_fact: dict[str, list[Claim]] = {}
    for claim in claims:
        by_fact.setdefault(claim.fact_id or claim.key.key_id, []).append(claim)
    cards: list[Card] = []
    for fact in sorted(facts, key=lambda f: f.fact_id):
        fact_id = fact.fact_id or fact.key.key_id
        sources = by_fact.get(fact_id, ())
        cards.append(Card(
            fact_id=fact_id,
            key_digest=digest_of({"key": fact.key.canonical()}),
            state=fact.state.value,
            value_digest=digest_of({"value": fact.value}) if fact.value is not None else "",
            claim_ids=tuple(sorted(c.claim_id for c in sources)),
            source_digests=tuple(sorted({c.source.digest for c in sources})),
            watermarks=(snapshot.knowledge_seq, snapshot.identity_generation,
                        int(snapshot.policy_version) if snapshot.policy_version.isdigit() else 0),
        ))
    return tuple(cards)


def card_digest(cards: tuple[Card, ...]) -> str:
    return digest_of({"cards": [c.digest() for c in cards]})
