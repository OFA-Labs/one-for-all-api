"""Candidate fusion and query orchestration (M10 CP10.4/10.5/10.6)."""
from __future__ import annotations

from dataclasses import dataclass

from ..auth.context import authorize, check_read_epoch
from ..config import V3Config
from ..contracts import (
    Action,
    Answer,
    AnswerStatus,
    AuthorizedContext,
    Candidate,
    CandidateSet,
    Claim,
    Decision,
    FactKey,
    IdentityEvent,
    PendingImpact,
    Selector,
    Snapshot,
    digest_of,
)
from ..errors import IncompatibleGeneration
from ..resolver.policy import PolicyVersion
from ..resolver.reducer import Resolver
from .arms import VectorArm, exact_candidates, graph_candidates, lexical_candidates
from .selectors import parse_selector

RRF_K0: int = 60
ARM_WEIGHTS: dict[str, float] = {"exact": 4.0, "lexical": 1.0, "graph:family": 0.5,
                                 "graph:dependency": 0.5, "graph:near_miss": 0.25,
                                 "vector": 1.0}


def fuse(arms: dict[str, tuple[Candidate, ...]]) -> tuple[Candidate, ...]:
    """Reciprocal rank fusion; absent arms contribute zero. Protected union survives."""
    scores: dict[str, float] = {}
    best: dict[str, Candidate] = {}
    protected: set[str] = set()
    for arm, candidates in arms.items():
        weight = ARM_WEIGHTS.get(arm, 1.0)
        for candidate in candidates:
            if candidate.protected:
                protected.add(candidate.fact_id)
            score = scores.get(candidate.fact_id, 0.0) + weight / (RRF_K0 + max(1, candidate.rank))
            scores[candidate.fact_id] = score
            existing = best.get(candidate.fact_id)
            if existing is None or candidate.protected or score > scores.get(existing.fact_id, 0):
                best[candidate.fact_id] = candidate.model_copy(update={"score": round(score, 8)})
    return tuple(sorted(
        (best[fid] for fid in best),
        key=lambda c: (c.fact_id not in protected, -c.score, c.fact_id),
    ))


@dataclass
class QueryService:
    cfg: V3Config
    policy: PolicyVersion
    vector: VectorArm | None = None

    def candidates(
        self,
        ctx: AuthorizedContext,
        selector: Selector,
        snapshot: Snapshot,
        claims: tuple[Claim, ...],
        *,
        edges: tuple[tuple[str, str, str], ...] = (),
        coverage_seq: int | None = None,
        incomplete: bool = False,
    ) -> CandidateSet:
        parse_selector(ctx, selector)
        check_read_epoch(ctx, snapshot)
        arms: dict[str, tuple[Candidate, ...]] = {
            "exact": exact_candidates(claims, selector),
            "lexical": lexical_candidates(claims, selector, self.cfg.query_max_candidates),
        }
        if self.cfg.graph_retrieval_enabled:
            arms.update({
                arm: tuple(c for c in graph_candidates(claims, selector, edges) if c.arm == arm)
                for arm in ("graph:family", "graph:dependency", "graph:near_miss")
            })
        if self.vector is not None:
            try:
                arms["vector"] = self.vector.candidates(claims, selector)
            except IncompatibleGeneration:
                arms["vector"] = ()
        selected = fuse(arms)[: self.cfg.query_max_candidates]
        return CandidateSet(
            candidates=selected,
            coverage_seq=coverage_seq if coverage_seq is not None else snapshot.knowledge_seq,
            complete=not incomplete,
            arms=tuple(sorted(arms)),
            degradation=(
                ("vector_unavailable",)
                if self.cfg.vector_retrieval_enabled
                and (self.vector is None or self.vector.manifest is None)
                else ()
            ),
        )

    def answer(
        self,
        ctx: AuthorizedContext,
        selector: Selector,
        snapshot: Snapshot,
        claims: tuple[Claim, ...],
        identity_events: tuple[IdentityEvent, ...],
        decisions: tuple[Decision, ...],
        pending: tuple[PendingImpact, ...],
        *,
        edges: tuple[tuple[str, str, str], ...] = (),
        incomplete: bool = False,
        suppressed: frozenset[str] = frozenset(),
    ) -> Answer:
        """CP10.6: one snapshot, M11 resolver, pending fences, final auth recheck."""
        authorize(ctx, predicate=selector.predicate or "*", action=Action.QUERY)
        candidate_set = self.candidates(
            ctx, selector, snapshot, claims, edges=edges, incomplete=incomplete
        )
        keys = tuple(dict.fromkeys(c.key for c in candidate_set.candidates))
        eligible_claims = tuple(
            c for c in claims if c.key.canonical() in {k.canonical() for k in keys}
        )
        resolved = list(Resolver(self.policy).resolve(
            eligible_claims, identity_events, decisions, pending, snapshot,
            suppressed=suppressed,
        ))
        from ..contracts import AnswerItem, FactState
        from ..resolver.types import ResolvedFact
        # An exact selector with no authoritative claim is an explicit absent
        # fact, not a silently missing facet.
        seen_keys = {r.key.canonical() for r in resolved}
        for candidate in candidate_set.candidates:
            if candidate.arm == "exact" and candidate.key.canonical() not in seen_keys:
                resolved.append(ResolvedFact(
                    key=candidate.key, fact_id=candidate.fact_id,
                    state=FactState.ABSENT,
                ))
                seen_keys.add(candidate.key.canonical())
        items: tuple[AnswerItem, ...] = tuple(r.to_answer_item() for r in resolved)
        check_read_epoch(ctx, snapshot)  # final authorization epoch check
        if not items or all(i.state is FactState.ABSENT for i in items):
            status = AnswerStatus.NOT_FOUND
        elif any(i.state in (FactState.CONFLICT, FactState.PENDING_VERIFICATION,
                            FactState.UNKNOWN) for i in items):
            status = AnswerStatus.PENDING if any(
                i.state is FactState.PENDING_VERIFICATION for i in items
            ) else AnswerStatus.AMBIGUOUS
        elif candidate_set.complete:
            status = AnswerStatus.COMPLETE
        else:
            status = AnswerStatus.PARTIAL
        degradation = tuple(candidate_set.degradation)
        if incomplete:
            degradation += ("index_lag",)
        return Answer(
            answer_status=status, items=items, snapshot=snapshot,
            degradation=tuple(dict.fromkeys(degradation)),
            completeness=() if candidate_set.complete else ("incomplete_candidate_set",),
            request_id=ctx.request_id,
            cursor=digest_of({"scope": ctx.scope, "seq": snapshot.knowledge_seq,
                              "cursor": ctx.request_id}),
        )
