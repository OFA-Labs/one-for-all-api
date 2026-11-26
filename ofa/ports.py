"""The seam between the core and whatever voice front end is attached (none for typed use).
The core is built against VoicePort; attaching a voice loop swaps behaviour without rewiring the core."""
from __future__ import annotations

import time
from typing import Awaitable, Callable

from .policy.approval import Heard

Speak = Callable[[str], Awaitable[float]]
Listen = Callable[[float], Awaitable["Heard | None"]]


class VoicePort:
    """Without a voice front end replies are only logged and nothing can be heard, so Tier 2 never runs."""

    def __init__(self, log: Callable[..., None] = lambda *a, **k: None):
        self._log = log
        self._speak: Speak | None = None
        self._listen: Listen | None = None
        self._listen_dictation: Listen | None = None
        self._pause_gate: Callable[[], Awaitable] | None = None
        self._display: Callable[[str, str | None], None] | None = None

    def attach(self, *, speak: Speak, listen: Listen, listen_dictation: Listen | None = None,
               pause_gate: Callable[[], Awaitable] | None = None,
               display: Callable[[str, str | None], None] | None = None) -> None:
        self._speak, self._listen = speak, listen
        self._listen_dictation, self._pause_gate, self._display = listen_dictation, pause_gate, display

    async def speak(self, text: str) -> float:
        if self._speak is None:
            self._log("say", text=text)
            return time.monotonic()
        return await self._speak(text)

    async def listen(self, timeout: float) -> Heard | None:
        return await self._listen(timeout) if self._listen else None

    async def listen_dictation(self, timeout: float) -> Heard | None:
        listener = self._listen_dictation or self._listen
        return await listener(timeout) if listener else None

    async def pause_gate(self) -> None:
        if self._pause_gate:
            await self._pause_gate()

    def display(self, state: str, caption: str | None = None) -> None:
        if self._display:
            self._display(state, caption)
