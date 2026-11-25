"""Traceability: C06."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from ebrain.v3.contracts import DecisionState
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.errors import StaleBase
from ebrain.v3.review.workflow import ReviewService

from ..v3_helpers import ctx, key, write


def test_C06_shared_observed_base(pg_ledger):
    from ..v3_helpers import write as make_write
    c = ctx()
    k = key()
    head = pg_ledger.admit(c, make_write("base", k, "base"))
    outcomes: list[str] = []

    def branch(n: int) -> None:
        try:
            pg_ledger.admit(c, make_write(f"b{n}", k, f"v{n}", idem=f"i{n}",
                                          head=head.claim_id))
            outcomes.append("ok")
        except StaleBase:
            outcomes.append("stale")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(branch, (1, 2)))
    assert "stale" in outcomes


def test_no_timestamp_winner_in_review():
    workflow = ReviewService()
    c = ctx()
    from ebrain.v3.contracts import Decision
    workflow.propose(c, Decision(
        decision_id="d", kind="correction", state=DecisionState.DRAFT, version=1,
        digest="x", scope=c.scope, targets=(), proposer=c.principal.subject,
    ))
    assert workflow.decisions["d"].state is DecisionState.DRAFT
