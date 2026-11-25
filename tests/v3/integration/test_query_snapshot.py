"""Traceability: H10."""
from __future__ import annotations

from ebrain.v3.contracts import AnswerStatus, Selector
from ebrain.v3.resolver.policy import DEFAULT_POLICY
from ebrain.v3.retrieval.query import QueryService

from ..v3_helpers import ctx


def test_H10_degraded_failures(pg_ledger):
    c = ctx()
    answer = QueryService(pg_ledger.cfg, DEFAULT_POLICY).answer(
        c, Selector(scope=c.scope), pg_ledger.snapshot(c), (), (), (), (),
        incomplete=True,
    )
    assert answer.answer_status in (AnswerStatus.NOT_FOUND, AnswerStatus.PARTIAL)
    assert "index_lag" in answer.degradation
    assert not any(i.state.value == "current" for i in answer.items)
