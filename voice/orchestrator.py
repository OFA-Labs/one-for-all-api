"""Voice approval is an adapter to executor authority, never its replacement."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Literal

from ofa_execution.contracts import Decision

EventKind = Literal[
    "plan_ready", "approval_required", "step_started", "step_done",
    "blocked", "completed", "failed",
]


@dataclass(frozen=True)
class VoiceEvent:
    kind: EventKind
    task_id: str
    sequence: int
    summary: str
    approval_id: str | None = None
    reading_hash: str | None = None


def approval_choice(text: str, confidence: float | None) -> bool | None:
    yes = {"yes", "approve", "haan kar do", "हाँ कर दो", "मंज़ूर"}
    no = {"no", "cancel", "ruko", "नहीं", "रुको"}
    phrase = " ".join(text.casefold().strip(".!?। ").split())
    if phrase in no:
        return False
    if confidence is None or confidence < 0.85:
        return None
    return True if phrase in yes else None


class VoiceApprovals:
    def __init__(self) -> None:
        self.pending: tuple[str, str, str, int, float] | None = None

    def offer(self, task: str, approval: str, reading: str,
              epoch: int, ttl: float = 60) -> None:
        self.pending = (task, approval, reading, epoch, time.monotonic() + ttl)

    def invalidate(self) -> None:
        self.pending = None

    def decide(self, text: str, confidence: float | None,
               epoch: int, engine: Any) -> str:
        if self.pending is None:
            return "NO_APPROVAL"
        task, approval, reading, offered_epoch, expiry = self.pending
        if epoch != offered_epoch or time.monotonic() >= expiry:
            self.invalidate()
            return "APPROVAL_EXPIRED"
        choice = approval_choice(text, confidence)
        if choice is None:
            return "APPROVAL_UNCLEAR"
        engine.decide(task, Decision(
            approval_id=approval, reading_hash=reading, approve=choice,
        ))
        self.invalidate()
        return "APPROVED" if choice else "CANCELLED"


class FakeOrchestrator:
    def __init__(self) -> None:
        self.decisions: list[tuple[str, bool]] = []

    def decide(self, task: str, decision: Decision) -> None:
        self.decisions.append((task, decision.approve))

    def events(self) -> list[VoiceEvent]:
        return [
            VoiceEvent("plan_ready", "fixture", 1, "Review a draft."),
            VoiceEvent("step_started", "fixture", 2, "Reading the fixture."),
            VoiceEvent("step_done", "fixture", 3, "Draft ready."),
            VoiceEvent("approval_required", "fixture", 4, "Approve sending this draft?",
                       "fixture-approval", "fixture-reading"),
            VoiceEvent("blocked", "fixture", 5, "Slack is not connected."),
            VoiceEvent("failed", "fixture", 6, "No message was sent."),
            VoiceEvent("completed", "fixture-complete", 1, "Read-only fixture finished."),
        ]
