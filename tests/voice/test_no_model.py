from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from voice.capabilities import CapabilityDispatcher, MissingCapability, Receipt, ReasoningGate
from voice.intent import Action, Router


class ModelSpy:
    def __init__(self) -> None:
        self.calls = 0

    async def stream(self, text: str, language: str) -> AsyncIterator[str]:
        self.calls += 1
        yield "fixture review content"


@pytest.mark.parametrize("phrase", [
    "launch WhatsApp", "bring up Slack", "Claude Code open karo", "open GitHub",
    "open Comet Desk", "focus Slack", "minimize Slack", "save review.md",
    "send this file to Slack channel engineering",
    'write "Open Slack and send it" to notes.md',
])
def test_routine_commands_have_zero_model_calls(phrase: str) -> None:
    async def run() -> None:
        router = Router({name.casefold(): name for name in [
            "WhatsApp", "Slack", "Claude Code", "GitHub", "Comet Desk"
        ]})
        intent = router.route(phrase)
        assert intent.intent != "clarify" and intent.actions
        assert all(a.capability != "reason.generate" for a in intent.actions)
        model = ModelSpy()
        gate = ReasoningGate(model)

        async def handler(action, context, command_id):
            return Receipt(True)

        dispatcher = CapabilityDispatcher({a.capability: handler for a in intent.actions}, gate)
        assert await dispatcher.execute(intent.actions, "en", "fixture")
        assert gate.calls == model.calls == 0
    asyncio.run(run())


def test_unknown_and_duplicate_names_never_become_reasoning() -> None:
    assert Router({"slack": "Slack"}).route("open an unknown app").intent == "clarify"
    assert Router([("claude", "desktop"), ("claude", "cli")]).route("open Claude").intent == "clarify"
    assert Router({"slack": "Slack"}).route("open Slack and delete files").actions == ()


def test_current_iteration_has_no_engine_and_future_contract_is_per_node() -> None:
    async def run() -> None:
        router = Router({"github": "GitHub", "slack": "Slack"})
        intent = router.route("open GitHub then review this PR then write review.md then open Slack then send this file to engineering")
        assert sum(a.capability == "reason.generate" for a in intent.actions) == 1
        observed: list[str] = []

        async def handler(action, context, command_id):
            observed.append(action.capability)
            return Receipt(True)

        handlers = {a.capability: handler for a in intent.actions if a.capability != "reason.generate"}
        current = CapabilityDispatcher(handlers, ReasoningGate(None))
        with pytest.raises(MissingCapability, match="OFA Engine"):
            await current.execute(intent.actions, "en", "current")
        assert observed == []
        model = ModelSpy()  # Future contract fixture only; no live model.
        future = CapabilityDispatcher(handlers, ReasoningGate(model))
        assert await future.execute(intent.actions, "en", "future", {
            "source_revision": "fixture-revision", "source_text": "fixture diff"
        })
        assert model.calls == 1 and len(observed) == 4
        with pytest.raises(PermissionError):
            await anext(ReasoningGate(model).stream(Action("target.open", {}), "en"))
    asyncio.run(run())
