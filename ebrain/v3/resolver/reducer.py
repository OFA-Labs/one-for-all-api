"""Pure ordered reduction to exactly zero or one scalar current per fact (M11 CP11.2/11.3).

Permutation invariant: inputs are sorted by committed sequence before reduction.
No UUID, equal timestamp, model score, retrieval rank or usage feedback ever
breaks a tie between incomparable competing values — those become a conflict.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import (
    Claim,
    Decision,
    FactKey,
    FactState,
    IdentityEvent,
    IdentityEventKind,
    PendingImpact,
    Provenance,
    Snapshot,
    digest_of,
)
from .eligibility import screen
from .intervals import freshness
from .policy import PolicyVersion
from .types import ResolvedFact


def _binding_map(events: tuple[IdentityEvent, ...], seq: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for event in sorted(events, key=lambda e: (e.knowledge_seq, e.event_id)):
        if event.knowledge_seq > seq or not event.claim_id or not event.fact_id:
            continue
        if event.kind in (
            IdentityEventKind.BIND, IdentityEventKind.MERGE, IdentityEventKind.SPLIT,
        ):
            out[event.claim_id] = event.fact_id
        elif event.kind is IdentityEventKind.UNBIND_CORRECTION:
            out.pop(event.claim_id, None)
    return out


def _value_digest(value: Any, unit: str | None) -> str:
    return digest_of({"value": value, "unit": unit})


def _current_group(claims: tuple[Claim, ...]) -> tuple[Claim | None, str]:
    """Return the single current representative and a decision annotation."""
    groups: dict[str, list[Claim]] = {}
    for claim in claims:
        groups.setdefault(_value_digest(claim.value, claim.unit), []).append(claim)
    if len(groups) == 1:
        representatives = sorted(next(iter(groups.values())), key=lambda c: c.claim_id)
        return representatives[0], "corroborated" if len(representatives) > 1 else "single"

    # A legitimate supersede chain: claim.base_seq points at the prior head's
    # committed sequence and the new claim has equal or higher admitted authority.
    superseded_by: set[str] = set()
    for claim in claims:
        for prior in claims:
            if (
                claim.base_seq == prior.knowledge_seq
                and claim.knowledge_seq > prior.knowledge_seq
                and claim.kind in ("assertion", "decision")
            ):
                superseded_by.add(prior.claim_id)
    tips = [c for c in claims if c.claim_id not in superseded_by]
    if len(tips) == 1:
        tip = tips[0]
        return tip, f"superseded:{len(claims) - 1}"
    # Competing branches from a shared base, or equal-authority incomparable
    # values: no timestamp/UUID tie-break is permitted.
    return None, f"conflict:{len(tips)}_tips"


@dataclass
class Resolver:
    policy: PolicyVersion

    def resolve(
        self,
        claims: tuple[Claim, ...],
        identity_events: tuple[IdentityEvent, ...],
        decisions: tuple[Decision, ...],
        pending: tuple[PendingImpact, ...],
        snapshot: Snapshot,
        *,
        valid_at: str | None = None,
        suppressed: frozenset[str] = frozenset(),
    ) -> tuple[ResolvedFact, ...]:
        valid_at = valid_at or snapshot.valid_at
        screening = screen(
            claims, policy=self.policy, pending=pending, decisions=decisions,
            valid_at=valid_at, knowledge_seq=snapshot.knowledge_seq,
            suppressed=suppressed,
        )
        bindings = _binding_map(identity_events, snapshot.knowledge_seq)
        grouped: dict[str, list[Claim]] = {}
        for eligible in screening.eligible:
            claim = eligible.claim
            fact_id = bindings.get(claim.claim_id) or claim.fact_id or claim.key.key_id
            grouped.setdefault(fact_id, []).append(claim)

        out: list[ResolvedFact] = []
        for fact_id in sorted(grouped):
            group = tuple(sorted(grouped[fact_id], key=lambda c: (c.knowledge_seq, c.claim_id)))
            key: FactKey = group[0].key
            canonical = key.canonical()
            if len({c.key.canonical() for c in group}) > 1:
                out.append(ResolvedFact(
                    key=key, fact_id=fact_id, state=FactState.CONFLICT,
                    annotations=("ambiguous_identity_mapping",),
                ))
                continue
            if canonical in screening.pending_keys:
                out.append(ResolvedFact(
                    key=key, fact_id=fact_id, state=FactState.PENDING_VERIFICATION,
                    annotations=("eligible_pending_impact",),
                ))
                continue
            if fact_id in screening.withdrawn_facts:
                out.append(ResolvedFact(
                    key=key, fact_id=fact_id, state=FactState.WITHDRAWN,
                    annotations=("reviewed_lifecycle_decision",),
                ))
                continue
            representative, annotation = _current_group(group)
            if representative is None:
                out.append(ResolvedFact(
                    key=key, fact_id=fact_id, state=FactState.CONFLICT,
                    annotations=(annotation,),
                ))
                continue
            source = representative.source
            prov = Provenance(
                source_id=source.source_id, revision=source.revision,
                digest=source.digest,
                freshness=freshness(representative, valid_at, snapshot.valid_at),
                contract=source.contract,
            )
            equivalents = sorted({
                code for c in group for code in c.equivalent_codes
                if _value_digest(c.value, c.unit) == _value_digest(representative.value, representative.unit)
            })
            out.append(ResolvedFact(
                key=key, fact_id=fact_id, state=FactState.CURRENT,
                value=representative.value, value_type=representative.value_type,
                provenance=(prov,), annotations=(annotation,),
                freshness=prov.freshness,
                representative_claim_id=representative.claim_id,
                equivalent_codes=tuple(equivalents),
            ))
        return tuple(out)
