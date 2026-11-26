"""Scripted engine for tests: each call pops the next list of events (or a callable)."""
from __future__ import annotations

import json
from typing import Callable

from .base import Done, EngineError, EngineInfo, EngineMetrics, HealthResult, TextDelta, ToolCall, Usage


def tool(name: str, **args) -> ToolCall:
    return ToolCall(f"c_{name}", name, json.dumps(args))


def say(text: str) -> TextDelta:
    return TextDelta(text)


class FakeEngine:
    def __init__(self, script: list | Callable | None = None, vision: bool = False):
        self.script = script if script is not None else []
        self.requests: list[dict] = []
        self._metrics = EngineMetrics()
        self.vision = vision

    def info(self) -> EngineInfo:
        return EngineInfo("fake", "fake", True, False, self.vision, 131072, 4096)

    def metrics(self) -> EngineMetrics:
        return self._metrics

    async def health(self) -> HealthResult:
        return HealthResult(True, "fake")

    async def stream(self, messages, tools, *, images=()):
        from ..egress import EGRESS, LeakBlocked
        body = {"messages": messages, "tools": tools}
        try:
            EGRESS.guard(body, "llm")
        except LeakBlocked:
            yield EngineError("LEAK_BLOCKED", False, "blocked")
            return
        self.requests.append(json.loads(json.dumps(body, default=str)))
        if callable(self.script):
            events = self.script(messages, tools)
        else:
            events = self.script.pop(0) if self.script else [TextDelta("Okay.")]
        for e in events:
            yield e
            if isinstance(e, EngineError):
                return
        self._metrics.record(Usage(1, 1, 1, 1))
        yield Done(Usage(1, 1, 1, 1), "tool_calls" if any(isinstance(e, ToolCall) for e in events) else "stop")
