from __future__ import annotations

from voice.orchestrator import FakeOrchestrator, VoiceApprovals, approval_choice


def test_approval_grammar() -> None:
    assert approval_choice("haan kar do", 0.95) is True
    assert approval_choice("हाँ कर दो", 0.95) is True
    assert approval_choice("yes", 0.4) is None
    assert approval_choice("yes", None) is None
    assert approval_choice("yes no", 0.99) is None
    assert approval_choice("ruko", None) is False


def test_approval_is_one_use_and_epoch_bound() -> None:
    approvals = VoiceApprovals()
    executor = FakeOrchestrator()
    approvals.offer("task", "approval", "reading", 2)
    assert approvals.decide("yes", 0.2, 2, executor) == "APPROVAL_UNCLEAR"
    assert not executor.decisions
    assert approvals.decide("yes", 0.99, 2, executor) == "APPROVED"
    assert executor.decisions == [("task", True)]
    assert approvals.decide("yes", 0.99, 2, executor) == "NO_APPROVAL"
    approvals.offer("task", "new", "reading", 2)
    assert approvals.decide("yes", 0.99, 3, executor) == "APPROVAL_EXPIRED"
    assert len(executor.decisions) == 1


def test_expired_and_cancelled_approval() -> None:
    approvals = VoiceApprovals()
    executor = FakeOrchestrator()
    approvals.offer("task", "old", "reading", 1, ttl=-1)
    assert approvals.decide("yes", 0.99, 1, executor) == "APPROVAL_EXPIRED"
    approvals.offer("task", "fresh", "reading", 1)
    assert approvals.decide("no", None, 1, executor) == "CANCELLED"
    assert executor.decisions == [("task", False)]
