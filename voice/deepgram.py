"""Documented Deepgram STT v1 and Flux TTS v2 wire adapters."""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import suppress
from urllib.parse import urlencode

from websockets.asyncio.client import connect

from .config import Settings
from .contracts import Audio, ProviderError, Transcript


async def _finish(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


class DeepgramStt:
    name = "deepgram"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        query = urlencode({
            "model": "nova-3", "language": "multi", "encoding": "linear16",
            "sample_rate": 24000, "channels": 1,
            "interim_results": "true", "endpointing": 200,
        })
        headers = {"Authorization": "Token " + self.settings.deepgram_key.get_secret_value()}
        uri = f"wss://{self.settings.deepgram_host}/v1/listen?{query}"
        async with connect(uri, additional_headers=headers, open_timeout=3,
                           max_size=131072, max_queue=8, proxy=None,
                           close_timeout=0.05) as ws:
            async def send() -> None:
                async for frame in frames:
                    await ws.send(frame)
                await ws.send(json.dumps({"type": "CloseStream"}))

            sender = asyncio.create_task(send())
            segments: list[str] = []
            confidences: list[float] = []
            final_sent = False
            try:
                async for raw in ws:
                    event = json.loads(raw)
                    if event.get("type") == "Error":
                        raise ProviderError("STT_DOWN")
                    if event.get("type") != "Results":
                        continue
                    alternative = event["channel"]["alternatives"][0]
                    text = alternative.get("transcript", "").strip()
                    if event.get("is_final") and text:
                        segments.append(text)
                        confidences.append(float(alternative.get("confidence", 0)))
                    elif text:
                        yield Transcript(" ".join([*segments, text]), False)
                    if event.get("speech_final") and segments:
                        final_sent = True
                        yield Transcript(" ".join(segments), True, min(confidences))
                        return
                await sender
                if segments and not final_sent:
                    yield Transcript(" ".join(segments), True, min(confidences))
            finally:
                await _finish(sender)

class DeepgramTts:
    name = "deepgram"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.voice = settings.english_voice

    def voice_for(self, language: str) -> str:
        return (self.settings.english_voice if language == "en"
                else self.settings.hindi_voice)

    async def stream(self, text: str, language: str) -> AsyncIterator[Audio]:
        query = urlencode({
            "model": self.voice_for(language), "encoding": "linear16",
            "sample_rate": 24000,
        })
        uri = f"wss://{self.settings.deepgram_host}/v2/speak?{query}"
        headers = {"Authorization": "Token " + self.settings.deepgram_key.get_secret_value()}
        async with connect(uri, additional_headers=headers, open_timeout=3,
                           max_size=1048576, max_queue=8, proxy=None,
                           close_timeout=0.05) as ws:
            await ws.send(json.dumps({"type": "Speak", "text": text}))
            await ws.send(json.dumps({"type": "Flush"}))
            async for raw in ws:
                if isinstance(raw, bytes):
                    yield Audio(raw)
                    continue
                event = json.loads(raw)
                if event.get("type") == "SpeechMetadata":
                    return
                if event.get("type") == "Error":
                    raise ProviderError("TTS_DOWN")
            raise ProviderError("TTS_TRUNCATED")
