"""Deepgram Flux STT (/v2/listen) with model-integrated end-of-turn detection (§4.1).
flux-general-multi covers en/hi (plus es, fr, de, ru, pt, ja, it, nl) per docs checked 2026-11-26."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from urllib.parse import urlencode

from websockets.asyncio.client import connect

from voice.contracts import ProviderError, Transcript


class FluxStt:
    name = "deepgram-flux"

    def __init__(self, key: str, model: str = "flux-general-multi", rate: int = 24000, eot_threshold: float = 0.8,
                 eot_timeout_ms: int = 3000, host: str = "api.deepgram.com"):
        self.key, self.model, self.rate, self.host = key, model, rate, host
        self.eot_threshold, self.eot_timeout_ms = eot_threshold, eot_timeout_ms
        self.events: list[str] = []

    async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        query = urlencode({"model": self.model, "encoding": "linear16", "sample_rate": self.rate,
                           "eot_threshold": self.eot_threshold, "eot_timeout_ms": self.eot_timeout_ms})
        uri = f"wss://{self.host}/v2/listen?{query}"
        async with connect(uri, additional_headers={"Authorization": "Token " + self.key}, open_timeout=5,
                           max_size=262144, proxy=None, close_timeout=0.2) as ws:
            async def send():
                async for frame in frames:
                    await ws.send(frame)
                # Give Flux trailing silence so it can close the turn, then close.
                silence = b"\x00\x00" * (self.rate // 10)
                for _ in range(12):
                    await ws.send(silence)
                    await asyncio.sleep(0.02)
                await ws.send(json.dumps({"type": "CloseStream"}))
            sender = asyncio.create_task(send())
            last = ""
            try:
                async for raw in ws:
                    if isinstance(raw, bytes):
                        continue
                    ev = json.loads(raw)
                    kind = ev.get("type")
                    self.events.append(f"{kind}:{ev.get('event', '')}")
                    if kind == "Error" or kind == "FatalError":
                        raise ProviderError("STT_DOWN")
                    if kind != "TurnInfo":
                        continue
                    text = (ev.get("transcript") or "").strip()
                    words = ev.get("words") or []
                    conf = min((float(w.get("confidence", 1)) for w in words), default=None)
                    if ev.get("event") == "EndOfTurn":
                        if text:
                            yield Transcript(text, True, conf)
                            return
                    elif text and text != last:
                        last = text
                        yield Transcript(text, False, conf)
                if last:
                    yield Transcript(last, True, None)
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await sender
