"""Capability-specific breakers and lossless pre-dispatch STT replay."""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable

from .config import Settings
from .contracts import Emit, ProviderError, SttProvider, Transcript
from .replay import ReplayFeed


class Breaker:
    def __init__(self, cooldown: float = 30,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.cooldown, self.clock = cooldown, clock
        self.until = 0.0
        self.probing = False
        self.permanent = False

    def allow(self) -> bool:
        if self.permanent or self.clock() < self.until:
            return False
        if self.until and self.probing:
            return False
        self.probing = bool(self.until)
        return True

    def release_probe(self) -> None:
        self.probing = False

    def success(self) -> None:
        self.until = 0.0
        self.probing = False

    def failure(self, error: Exception) -> None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
        self.permanent = status in {401, 403} or (
            isinstance(error, ProviderError) and error.permanent
        )
        self.until = self.clock() + self.cooldown
        headers = getattr(response, "headers", {})
        retry_after = headers.get("Retry-After", "")
        try:
            self.until = max(self.until, self.clock() + float(retry_after))
        except (ValueError, TypeError):
            pass
        self.probing = False


class SttChain:
    def __init__(self, settings: Settings, providers: dict[str, SttProvider],
                 breakers: dict[str, Breaker], emit: Emit) -> None:
        self.settings, self.providers = settings, providers
        self.breakers, self.emit = breakers, emit

    async def transcribe(self, feed: ReplayFeed) -> AsyncIterator[Transcript]:
        for name in self.settings.stt_order:
            breaker = self.breakers[name]
            if not breaker.allow():
                continue
            if name == "gradium" and self.settings.language in {"hi", "hinglish"}:
                breaker.release_probe()
                self.emit("degraded", {"code": "LANGUAGE_DEGRADED"})
                continue
            iterator = self.providers[name].stream(feed.read())
            try:
                result = await asyncio.wait_for(
                    anext(iterator), timeout=self.settings.first_stt_seconds
                )
                self.emit("stt_first_event", {"provider": name})
                while True:
                    yield result
                    if result.final:
                        breaker.success()
                        return
                    result = await asyncio.wait_for(anext(iterator), timeout=3)
            except asyncio.CancelledError:
                breaker.release_probe()
                raise
            except Exception as exc:
                breaker.failure(exc)
                self.emit("provider_failed", {"provider": name, "capability": "stt"})
            finally:
                await iterator.aclose()
        raise ProviderError("STT_DOWN")
