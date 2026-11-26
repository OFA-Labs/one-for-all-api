"""Exact, lexical, graph and optional vector candidate arms.

All arms are scoped and authorized before execution. No arm may mutate identity
or current state. Model/vector arms are disabled unless a pinned manifest and an
approved generation are supplied.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..config import V3Config
from ..contracts import Candidate, Claim, Selector
from ..models.manifest import ModelManifest

_TOK = re.compile(r"[a-z0-9]+")


def exact_candidates(claims: tuple[Claim, ...], selector: Selector) -> tuple[Candidate, ...]:
    """Exact qualified key/fact id: always protected, never reranked away."""
    out: list[Candidate] = []
    for claim in claims:
        if selector.scope and claim.key.scope != selector.scope:
            continue
        if selector.fact_id and claim.fact_id != selector.fact_id:
            continue
        if selector.predicate and claim.key.predicate != selector.predicate:
            continue
        if selector.resource_id and claim.key.resource_id != selector.resource_id:
            continue
        if selector.qualifiers and not all(pair in claim.key.qualifiers for pair in selector.qualifiers):
            continue
        out.append(Candidate(
            fact_id=claim.fact_id or claim.key.key_id,
            key=claim.key, arm="exact", rank=1, score=1.0,
            protected=True, knowledge_seq=claim.knowledge_seq,
            provenance_digest=claim.digest,
        ))
    return tuple(sorted(out, key=lambda c: (c.fact_id, c.knowledge_seq)))


def lexical_candidates(
    claims: tuple[Claim, ...], selector: Selector, limit: int = 20
) -> tuple[Candidate, ...]:
    """Deterministic scoped lexical arm (pure token overlap; Postgres FTS seam in db)."""
    if not selector.text:
        return ()
    terms = set(_TOK.findall(selector.text.lower()))
    scored: list[tuple[float, Claim]] = []
    for claim in claims:
        if claim.key.scope != selector.scope:
            continue
        haystack = " ".join(
            [claim.key.resource_id, claim.key.predicate,
             *[v for _, v in claim.key.qualifiers], str(claim.value)]
        ).lower()
        tokens = set(_TOK.findall(haystack))
        score = len(terms & tokens) / len(terms | tokens) if terms | tokens else 0.0
        if score > 0:
            scored.append((score, claim))
    scored.sort(key=lambda pair: (-pair[0], pair[1].claim_id))
    return tuple(
        Candidate(
            fact_id=c.fact_id or c.key.key_id, key=c.key, arm="lexical",
            rank=i + 1, score=round(score, 6), knowledge_seq=c.knowledge_seq,
            provenance_digest=c.digest,
        )
        for i, (score, c) in enumerate(scored[:limit])
    )


def graph_candidates(
    claims: tuple[Claim, ...], selector: Selector, edges: tuple[tuple[str, str, str], ...]
) -> tuple[Candidate, ...]:
    """Graph edges give family/dependency/near-miss relations, NEVER identity or authority."""
    by_id = {c.fact_id or c.key.key_id: c for c in claims}
    seeds = {c.fact_id for c in exact_candidates(claims, selector)}
    out: list[Candidate] = []
    for source, relation, target in edges:
        if relation not in ("family", "dependency", "near_miss"):
            continue
        if source in seeds and target in by_id:
            claim = by_id[target]
            out.append(Candidate(
                fact_id=target, key=claim.key, arm=f"graph:{relation}", rank=1,
                score=0.5, knowledge_seq=claim.knowledge_seq,
                provenance_digest=claim.digest,
            ))
    return tuple(out)


@dataclass(frozen=True)
class VectorArm:
    cfg: V3Config
    manifest: ModelManifest | None = None

    def candidates(self, claims: tuple[Claim, ...], selector: Selector) -> tuple[Candidate, ...]:
        """Disabled or incompatible vector space contributes zero candidates."""
        if not self.cfg.vector_retrieval_enabled or self.manifest is None:
            return ()
        # No external model is invoked. A pinned, injected local encoder would
        # produce candidates here; its generation must match the query generation.
        return ()
