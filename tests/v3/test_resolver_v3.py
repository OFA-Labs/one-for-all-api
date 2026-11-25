"""M11 deterministic resolver, bitemporal and concurrency tests."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from ebrain.v3.auth.context import authorize
from ebrain.v3.clocks import FakeClock
from ebrain.v3.config import V3Config
from ebrain.v3.contracts import (
    AUTHORITY_RANK,
    Action,
    Claim,
    ClaimKind,
    Decision,
    DecisionState,
    FactState,
    PendingImpact,
    Snapshot,
    SourceContract,
    SourceRevision,
)
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.errors import Forbidden, StaleBase
from ebrain.v3.resolver.policy import DEFAULT_POLICY, PolicyVersion
from ebrain.v3.resolver.reducer import Resolver
from ebrain.v3.review.workflow import ReviewService

from .v3_helpers import ORG, SCOPE, ctx, key, ledger, write


def claim(claim_id: str, value: object, *, seq: int, valid_from: str | None = None,
          valid_to: str | None = None, base_seq: int = 0, authority: str = "human",
          kind: ClaimKind = ClaimKind.ASSERTION,
          contract: SourceContract = SourceContract.FIRST_PARTY_DECLARED,
          resource_id: str = "svc") -> Claim:
    k = key(resource_id=resource_id)
    return Claim(
        claim_id=claim_id, key=k, kind=kind, value=value,
        source=SourceRevision(source_id="s", revision="1", digest=f"d-{claim_id}",
                             parser_version="v1", contract=contract),
        principal_id="alice", authority=authority,  # type: ignore[arg-type]
        valid_from=valid_from or f"2026-01-0{seq}T00:00:00+00:00" if seq < 10 else f"2026-01-{seq}T00:00:00+00:00",
        valid_to=valid_to, recorded_at=f"2026-02-0{seq}T00:00:00+00:00",
        knowledge_seq=seq, base_seq=base_seq, digest=f"dg-{claim_id}", fact_id=k.key_id,
    )


def snap(seq: int, valid_at: str = "2026-03-01T00:00:00+00:00") -> Snapshot:
    return Snapshot(org_id=ORG, knowledge_seq=seq, valid_at=valid_at, policy_version="1")


def test_H09_intended_observation_distinct_and_freshness():
    intended = claim("c1", "active", seq=1, kind=ClaimKind.ASSERTION,
                     valid_to="2026-02-01T00:00:00+00:00")
    observed = claim("c2", "inactive", seq=2, kind=ClaimKind.OBSERVATION,
                     valid_to="2026-04-01T00:00:00+00:00", base_seq=1)
    resolved = Resolver(DEFAULT_POLICY).resolve(
        (intended, observed), (), (), (), snap(2, "2026-03-01T00:00:00+00:00")
    )
    current = [r for r in resolved if r.state is FactState.CURRENT]
    assert len(current) == 1
    assert current[0].value == "inactive"
    assert current[0].provenance[0].freshness == "fresh"
    # An expired observed value is last-known/unknown, never current.
    expired = Resolver(DEFAULT_POLICY).resolve(
        (intended,), (), (), (), snap(2, "2026-05-01T00:00:00+00:00")
    )
    assert all(r.state is not FactState.CURRENT for r in expired)


def test_external_and_derived_never_current():
    external = claim("e1", "poison", seq=1, contract=SourceContract.EXTERNAL_OBSERVATION)
    derived = claim("d1", "summary", seq=2, kind=ClaimKind.DERIVED)
    resolved = Resolver(DEFAULT_POLICY).resolve((external, derived), (), (), (), snap(2))
    assert all(r.state is not FactState.CURRENT for r in resolved)


def test_C06_conflict_from_shared_base_not_timestamp_winner():
    base = claim("c0", "base", seq=1)
    branch_a = claim("a", "A", seq=3, base_seq=1)
    branch_b = claim("b", "B", seq=2, base_seq=1)
    resolved = Resolver(DEFAULT_POLICY).resolve(
        (base, branch_a, branch_b), (), (), (), snap(3)
    )
    conflict = [r for r in resolved if r.state is FactState.CONFLICT]
    assert len(conflict) == 1
    assert "2_tips" in conflict[0].annotations[0]


def test_permutation_invariance():
    claims = (claim("c0", "base", seq=1), claim("a", "A", seq=3, base_seq=1),
              claim("b", "B", seq=2, base_seq=1))
    resolver = Resolver(DEFAULT_POLICY)
    a = resolver.resolve(claims, (), (), (), snap(3))
    b = resolver.resolve(tuple(reversed(claims)), (), (), (), snap(3))
    assert [r.state for r in a] == [r.state for r in b]


def test_equivalent_values_corroborate_not_duplicate_current():
    c1 = claim("c1", "v1", seq=1)
    c2 = claim("c2", "v1", seq=2, base_seq=1)
    resolved = Resolver(DEFAULT_POLICY).resolve((c1, c2), (), (), (), snap(2))
    current = [r for r in resolved if r.state is FactState.CURRENT]
    assert len(current) == 1
    assert current[0].annotations == ("corroborated",)


def test_C05_bitemporal_cuts_late_and_future():
    old = claim("old", "old-value", seq=1, valid_from="2026-01-01T00:00:00+00:00")
    late = claim("late", "new-value", seq=5, valid_from="2026-01-15T00:00:00+00:00", base_seq=1)
    resolver = Resolver(DEFAULT_POLICY)
    as_known_before = resolver.resolve((old, late), (), (), (),
                                       snap(4, "2026-02-01T00:00:00+00:00"))
    assert [r.value for r in as_known_before if r.state is FactState.CURRENT] == ["old-value"]
    as_known_after = resolver.resolve((old, late), (), (), (),
                                      snap(5, "2026-02-01T00:00:00+00:00"))
    assert [r.value for r in as_known_after if r.state is FactState.CURRENT] == ["new-value"]
    future = resolver.resolve((late,), (), (), (), snap(5, "2026-01-02T00:00:00+00:00"))
    assert all(r.state is not FactState.CURRENT for r in future)


def test_pending_impact_suppresses_current():
    c = claim("c1", "v", seq=1)
    k = key()
    pending = (PendingImpact(impact_id="p1", scope=SCOPE, key=k, reason="ambiguous",
                             created_seq=2, claim_id="c1"),)
    resolved = Resolver(DEFAULT_POLICY).resolve((c,), (), (), pending, snap(2))
    assert resolved[0].state is FactState.PENDING_VERIFICATION
    assert resolved[0].value is None


def test_M08_unsafe_policy_manifest_refused():
    with pytest.raises(Exception):
        PolicyVersion.from_manifest({
            "version": "2", "effective_seq": 1,
            "allow_external_current": True,
        })


def test_review_CAS_and_separation_of_duties():
    from ebrain.v3.contracts import Vote
    c = ctx()
    workflow = ReviewService()
    decision = Decision(
        decision_id="d1", kind="merge", state=DecisionState.DRAFT, version=1,
        digest="abc", scope=SCOPE, targets=(key().key_id,), proposer="alice",
    )
    workflow.propose(c, decision)
    workflow.submit(c, "d1")
    workflow.vote(ctx(subject="bob"), Vote(decision_id="d1", version=1,
                                           approve=False, digest="abc", voter="bob"))
    with pytest.raises(Exception):
        workflow.vote(ctx(subject="alice"), Vote(decision_id="d1", version=1,
                                                 approve=True, digest="abc", voter="alice"))
    with pytest.raises(Exception):
        workflow.decide(c, "d1", True)  # proposer cannot self-approve high risk
    workflow.vote(ctx(subject="carol"), Vote(decision_id="d1", version=1, approve=True,
                                             digest="abc", voter="carol"))
    workflow.vote(ctx(subject="dave"), Vote(decision_id="d1", version=1, approve=True,
                                           digest="abc", voter="dave"))
    approved = workflow.decide(ctx(subject="carol"), "d1", True)
    assert approved.state is DecisionState.APPROVED
    applied = workflow.apply(ctx(subject="dave"), "d1", seq=3)
    assert applied.applied_seq == 3
    with pytest.raises(Exception):
        workflow.apply(ctx(subject="dave"), "d1", seq=4)


def test_C10_logical_rollback_keeps_history():
    workflow = ReviewService()
    c = ctx()
    original = Decision(
        decision_id="d1", kind="correction", state=DecisionState.APPLIED, version=1,
        digest="d1digest", scope=SCOPE, targets=(key().key_id,), proposer="alice",
        applied_seq=3,
    )
    workflow.decisions["d1"] = original
    rollback = workflow.compensating_rollback(c, original=original, reason="reversed", seq=8)
    assert rollback.decision_id != original.decision_id
    assert workflow.decisions["d1"] is original
    assert rollback.applied_seq == 8


def test_M03_unowned_review_stays_blocked():
    workflow = ReviewService()
    c = ctx()
    workflow.propose(c, Decision(
        decision_id="d2", kind="policy", state=DecisionState.DRAFT, version=1,
        digest="x", scope=SCOPE, targets=(), proposer="alice", expires_at="2026-01-01",
    ))
    workflow.submit(c, "d2")
    assert len(workflow.blocked_queue(c)) == 1
    with pytest.raises(Exception):
        workflow.decide(c, "d2", True)


def test_C06_competing_threads_stale_base_rejected():
    led = ledger()
    c = ctx()
    k = key()
    first = led.admit(c, write("o1", k, "base", head=None))
    results: list[str] = []

    def writer(n: int) -> None:
        try:
            led.admit(c, write(f"o{n}", k, f"v{n}", idem=f"i{n}", head=first.claim_id))
            results.append("ok")
        except StaleBase:
            results.append("stale")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(writer, (2, 3)))
    # Both writers observed the same head; the second must not silently overwrite
    # with an obsolete base. One of them may apply, but the other sees stale head.
    assert "stale" in results
