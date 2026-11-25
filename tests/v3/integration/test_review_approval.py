"""Traceability: C09, M03."""
from __future__ import annotations

import pytest

from ebrain.v3.contracts import Decision, DecisionState, Vote
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.errors import Forbidden, StaleReview
from ebrain.v3.review.workflow import ReviewService

from ..v3_helpers import ctx, key


def _decision(scope: str) -> Decision:
    return Decision(
        decision_id="d1", kind="merge", state=DecisionState.DRAFT, version=1,
        digest="digest-1", scope=scope, targets=(key().key_id,), proposer="alice",
        expires_at="2030-01-01T00:00:00+00:00",
    )


def test_C09_digest_and_current_grant(pg_ledger):
    workflow = ReviewService()
    c = ctx()
    workflow.propose(c, _decision(c.scope))
    workflow.submit(c, "d1")
    with pytest.raises(StaleReview):
        workflow.vote(ctx(subject="bob"), Vote(
            decision_id="d1", version=2, approve=True, digest="digest-1", voter="bob"))
    workflow.vote(ctx(subject="bob"), Vote(
        decision_id="d1", version=1, approve=True, digest="digest-1", voter="bob"))
    with pytest.raises(Forbidden):
        workflow.decide(c, "d1", True)
    workflow.vote(ctx(subject="carol"), Vote(
        decision_id="d1", version=1, approve=True, digest="digest-1", voter="carol"))
    assert workflow.decide(ctx(subject="carol"), "d1", True).state is DecisionState.APPROVED


def test_M03_unowned_overdue_queue():
    workflow = ReviewService()
    c = ctx()
    workflow.propose(c, _decision(c.scope))
    workflow.submit(c, "d1")
    assert workflow.blocked_queue(c)
    with pytest.raises(Exception):
        workflow.decide(c, "d1", True)
