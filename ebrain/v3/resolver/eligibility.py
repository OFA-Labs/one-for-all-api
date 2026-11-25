"""Eligibility screen (M11 CP11.1).

Forbidden deciding inputs are never read here: no model score, no card current
field, no retrieval order and no client usage feedback. Intended decisions and
observed runtime state remain separate claim kinds.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import (
    AUTHORITY_RANK,
    Claim,
    ClaimKind,
    Decision,
    DecisionState,
    PendingImpact,
    SourceContract,
)
from .intervals import includes
from .policy import PolicyVersion


@dataclass(frozen=True)
class EligibleClaim:
    claim: Claim
    reason: str = "eligible"


@dataclass(frozen=True)
class Screening:
    eligible: tuple[EligibleClaim, ...]
    excluded: tuple[tuple[str, str], ...]  # (claim_id, reason)
    pending_keys: frozenset[str]
    withdrawn_facts: frozenset[str]


def screen(
    claims: tuple[Claim, ...],
    *,
    policy: PolicyVersion,
    pending: tuple[PendingImpact, ...],
    decisions: tuple[Decision, ...],
    valid_at: str,
    knowledge_seq: int,
    suppressed: frozenset[str] = frozenset(),
) -> Screening:
    eligible: list[EligibleClaim] = []
    excluded: list[tuple[str, str]] = []
    for claim in sorted(claims, key=lambda c: (c.knowledge_seq, c.claim_id)):
        if claim.knowledge_seq > knowledge_seq:
            excluded.append((claim.claim_id, "not_known_at_cut"))
            continue
        if claim.fact_id and claim.fact_id in suppressed:
            excluded.append((claim.claim_id, "suppressed"))
            continue
        if claim.kind not in (ClaimKind.ASSERTION, ClaimKind.OBSERVATION, ClaimKind.DECISION):
            excluded.append((claim.claim_id, "non_primary_kind"))
            continue
        if claim.source.contract not in (
            SourceContract.FIRST_PARTY_DECLARED, SourceContract.APPROVED_ARTIFACT
        ) or claim.source.retracted or claim.source.partial_scan:
            excluded.append((claim.claim_id, "source_not_eligible"))
            continue
        if AUTHORITY_RANK[claim.authority] < policy.required_rank(claim.key.predicate):
            excluded.append((claim.claim_id, "insufficient_admitted_authority"))
            continue
        if not includes(claim, valid_at, allow_unknown=policy.allow_unknown_valid_time):
            excluded.append((claim.claim_id, "outside_valid_interval"))
            continue
        eligible.append(EligibleClaim(claim))

    pending_keys = frozenset(
        p.key.canonical() for p in pending if p.active and p.key is not None
    )
    withdrawn = frozenset(
        target for d in decisions
        if d.state in (DecisionState.APPLIED, DecisionState.APPROVED)
        and d.kind in ("withdraw", "retire", "tombstone")
        for target in d.targets
    )
    return Screening(tuple(eligible), tuple(excluded), pending_keys, withdrawn)
