"""Complete fake speech-to-action-to-audio smoke; audio is synthetic tone only."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from uuid import uuid4

from .config import Settings
from .failover import Breaker, SttChain
from .fakes import FakeBridge, FakeStt, FakeTts
from .intent import Router
from .replay import ReplayFeed
from .tts.ack_cache import AckCache


async def run() -> None:
    settings = Settings()
    events: list[str] = []
    emit = lambda kind, payload: events.append(kind)
    bridge = FakeBridge()
    stt = SttChain(settings,
                   {"deepgram": FakeStt(), "gradium": FakeStt()},
                   {"deepgram": Breaker(), "gradium": Breaker()}, emit)
    feed = ReplayFeed()
    await feed.push(bytes(960))
    await feed.end()
    async for transcript in stt.transcribe(feed):
        if not transcript.final:
            continue
        intent = Router({"whatsapp": "WhatsApp"}).route(transcript.text)
        assert intent.intent == "open_app"
        assert await bridge.open(intent.slots["app"], str(uuid4()))
        events.append("launch_verified")
    with tempfile.TemporaryDirectory() as directory:
        cache = AckCache(FakeTts(), Path(directory), "fake")
        await cache.warm()
        assert cache.get("en")
        events.append("synthetic_ack_ready")
    print(json.dumps({"mode": "fake", "launches": len(bridge.commands), "events": events}))
    print("FAKE_PIPELINE_OK")


if __name__ == "__main__":
    asyncio.run(run())
