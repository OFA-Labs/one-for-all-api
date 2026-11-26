from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from voice.config import Settings
from voice.contracts import ProviderError, Transcript
from voice.failover import Breaker, SttChain
from voice.fakes import FakeStt
from voice.replay import ReplayFeed


def test_breaker_single_half_open_probe() -> None:
    now = [0.0]
    breaker = Breaker(10, lambda: now[0])
    assert breaker.allow()
    breaker.failure(RuntimeError())
    assert not breaker.allow()
    now[0] = 11
    assert breaker.allow()
    assert not breaker.allow()
    breaker.success()
    assert breaker.allow()


def test_permanent_auth_failure() -> None:
    breaker = Breaker()
    breaker.failure(ProviderError("AUTH", permanent=True))
    assert not breaker.allow()


def test_stt_replays_and_emits_one_final() -> None:
    class Drop:
        name = "drop"

        async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
            async for _ in frames:
                yield Transcript("open", False)
                raise ProviderError("SOCKET_DROPPED")

    class Observe(FakeStt):
        def __init__(self) -> None:
            super().__init__()
            self.received: list[bytes] = []

        async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
            async for chunk in frames:
                self.received.append(chunk)
            yield Transcript("open WhatsApp", True, 0.99)

    async def run() -> None:
        feed = ReplayFeed()
        await feed.push(b"abcd")
        await feed.push(b"efgh")
        await feed.end()
        second = Observe()
        chain = SttChain(Settings(), {"deepgram": Drop(), "gradium": second},
                         {"deepgram": Breaker(), "gradium": Breaker()},
                         lambda kind, payload: None)
        results = [event async for event in chain.transcribe(feed)]
        assert second.received == [b"abcd", b"efgh"]
        assert sum(event.final for event in results) == 1
    asyncio.run(run())


def test_provider_order_is_configuration_only() -> None:
    async def run() -> None:
        feed = ReplayFeed()
        await feed.push(b"ab")
        await feed.end()
        settings = Settings(stt_order=("gradium", "deepgram"))
        chain = SttChain(settings,
                         {"deepgram": FakeStt("primary"), "gradium": FakeStt("fallback")},
                         {"deepgram": Breaker(), "gradium": Breaker()},
                         lambda kind, payload: None)
        finals = [event.text async for event in chain.transcribe(feed) if event.final]
        assert finals == ["fallback"]
    asyncio.run(run())
