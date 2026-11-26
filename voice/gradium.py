"""Gradium JSON/base64 streams with explicit PCM24 format and English scope."""
from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator
from contextlib import suppress

from websockets.asyncio.client import connect

from .config import Settings
from .contracts import Audio, ProviderError, Transcript


class GradiumStt:
    name = "gradium"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        headers = {"x-api-key": self.settings.gradium_key.get_secret_value()}
        async with connect(
            "wss://api.gradium.ai/api/speech/asr", additional_headers=headers,
            open_timeout=3, max_size=131072, max_queue=8, proxy=None,
            close_timeout=0.05,
        ) as ws:
            await ws.send(json.dumps({
                "type": "setup", "model_name": "default", "input_format": "pcm",
                "json_config": {"language": "en", "delay_in_frames": 7},
            }))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            if ready.get("type") != "ready" or ready.get("sample_rate") != 24000:
                raise ProviderError("STT_FORMAT")

            async def send() -> None:
                buffer = bytearray()
                async for frame in frames:
                    buffer.extend(frame)
                    while len(buffer) >= 3840:
                        chunk = bytes(buffer[:3840])
                        del buffer[:3840]
                        await ws.send(json.dumps({
                            "type": "audio", "audio": base64.b64encode(chunk).decode(),
                        }))
                if buffer:
                    buffer.extend(bytes(3840 - len(buffer)))
                    await ws.send(json.dumps({
                        "type": "audio",
                        "audio": base64.b64encode(bytes(buffer)).decode(),
                    }))
                await ws.send(json.dumps({"type": "end_of_stream"}))

            sender = asyncio.create_task(send())
            parts: list[str] = []
            try:
                async for raw in ws:
                    event = json.loads(raw)
                    if event.get("type") == "text":
                        parts.append(event["text"])
                        yield Transcript(" ".join(parts), False, language="en")
                    elif event.get("type") == "end_of_stream":
                        await sender
                        yield Transcript(" ".join(parts), True, language="en")
                        return
                    elif event.get("type") == "error":
                        raise ProviderError("STT_DOWN")
                raise ProviderError("STT_TRUNCATED")
            finally:
                sender.cancel()
                with suppress(asyncio.CancelledError):
                    await sender


class GradiumTts:
    name = "gradium"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.voice = settings.gradium_voice

    async def stream(self, text: str, language: str) -> AsyncIterator[Audio]:
        if language != "en":
            raise ProviderError("LANGUAGE_DEGRADED", permanent=True)
        headers = {"x-api-key": self.settings.gradium_key.get_secret_value()}
        async with connect(
            "wss://api.gradium.ai/api/speech/tts", additional_headers=headers,
            open_timeout=3, max_size=1048576, max_queue=8, proxy=None,
            close_timeout=0.05,
        ) as ws:
            await ws.send(json.dumps({
                "type": "setup", "model_name": "default", "voice_id": self.voice,
                "output_format": "pcm_24000",
            }))
            ready = json.loads(await asyncio.wait_for(ws.recv(), timeout=3))
            if ready.get("type") != "ready" or ready.get("sample_rate") != 24000:
                raise ProviderError("TTS_FORMAT")
            await ws.send(json.dumps({"type": "text", "text": text}))
            await ws.send(json.dumps({"type": "end_of_stream"}))
            async for raw in ws:
                event = json.loads(raw)
                if event.get("type") == "audio":
                    yield Audio(base64.b64decode(event["audio"], validate=True))
                elif event.get("type") == "end_of_stream":
                    return
                elif event.get("type") == "error":
                    raise ProviderError("TTS_DOWN")
            raise ProviderError("TTS_TRUNCATED")
