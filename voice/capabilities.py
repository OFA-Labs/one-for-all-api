"""Routine handlers have no model handle; only explicit reasoning nodes cross it."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from dataclasses import dataclass, field

from .contracts import LlmProvider
from .intent import Action


class MissingCapability(Exception):
    pass


class ReasoningGate:
    def __init__(self, provider: LlmProvider | None) -> None:
        self._provider = provider
        self.calls = 0

    @property
    def available(self) -> bool:
        return self._provider is not None

    async def stream(self, action: Action, language: str,
                     context: Mapping[str, str] | None = None) -> AsyncIterator[str]:
        if action.capability != "reason.generate":
            raise PermissionError("Routine capabilities cannot invoke a model")
        source = context or {}
        if action.args.get("kind") == "review_pr" and not all(
            source.get(key) for key in ("source_revision", "source_text")
        ):
            raise MissingCapability("Select and fetch a specific PR revision first")
        if self._provider is None:
            raise MissingCapability("OFA Engine is not implemented in this iteration")
        request = json.dumps({
            "user_request": action.args.get("request", action.args.get("subject", "")),
            "source_revision": source.get("source_revision", ""),
            "source_text": source.get("source_text", "")[:24000],
        }, ensure_ascii=False)
        self.calls += 1
        async for token in self._provider.stream(request, language):
            yield token


@dataclass(frozen=True)
class Receipt:
    verified: bool
    facts: dict[str, str] = field(default_factory=dict)


Handler = Callable[[Action, Mapping[str, str], str], Awaitable[Receipt]]


class CapabilityDispatcher:
    def __init__(self, handlers: Mapping[str, Handler], reasoning: ReasoningGate) -> None:
        self._handlers = dict(handlers)
        self._reasoning = reasoning
        self.bindings: dict[str,str] = {}

    async def execute(self, actions: tuple[Action, ...], language: str,
                      command_id: str, bindings: Mapping[str, str] | None = None) -> bool:
        missing = {action.capability for action in actions
                   if action.capability != "reason.generate" and action.capability not in self._handlers}
        if missing:
            raise MissingCapability("Not connected: " + ", ".join(sorted(missing)))
        if any(a.capability == "reason.generate" for a in actions) and not self._reasoning.available:
            raise MissingCapability("OFA Engine is not implemented in this iteration")
        context = dict(self.bindings if bindings is None else bindings)
        context.pop("dispatch_only",None)
        context.pop("browser",None)  # A selected browser applies only to this compound request.
        for index, action in enumerate(actions):
            if action.capability == "reason.generate":
                chunks = [token async for token in self._reasoning.stream(action, language, context)]
                context["generated_text"] = "".join(chunks)
                continue
            before = self._reasoning.calls
            receipt = await self._handlers[action.capability](
                action, context, command_id + ":" + str(index)
            )
            if self._reasoning.calls != before:
                raise PermissionError("A routine adapter crossed the model boundary")
            if not receipt.verified:
                return False
            context.update(receipt.facts)
            self.bindings.update({key:value for key,value in context.items() if key not in {"browser","dispatch_only"}})
        return True
