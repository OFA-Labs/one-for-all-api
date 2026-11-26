"""No keys, microphone or external side effects in deterministic fake mode."""
from __future__ import annotations

import asyncio
import math
import struct
from collections.abc import AsyncIterator

from .contracts import Audio, ProviderError, Transcript


class FakeStt:
    name = "fake"

    def __init__(self, text: str = "open WhatsApp", fail: bool = False) -> None:
        self.text = text
        self.fail = fail

    async def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        if self.fail:
            raise ProviderError("STT_DOWN")
        first = True
        async for frame in frames:
            if frame and first:
                yield Transcript(self.text[:4], False)
                first = False
        yield Transcript(self.text, True, 0.99, "en")


class FakeTts:
    name = "fake"
    voice = "synthetic-tone-v1"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def stream(self, text: str, language: str) -> AsyncIterator[Audio]:
        self.calls += 1
        if self.fail:
            raise ProviderError("TTS_DOWN")
        samples = [int(800 * math.sin(2 * math.pi * 440 * n / 24000))
                   for n in range(2400)]
        pcm = struct.pack("<" + "h" * len(samples), *samples)
        await asyncio.sleep(0)
        yield Audio(pcm)


class FakeLlm:
    async def stream(self, text: str, language: str) -> AsyncIterator[str]:
        replies = {
            "en": "I am ready. What should I open?",
            "hi": "मैं तैयार हूँ। कौन सा ऐप खोलूँ?",
            "hinglish": "Main taiyar hoon. Kaunsa app kholun?",
        }
        for word in replies[language].split():
            await asyncio.sleep(0)
            yield word + " "


class FakeBridge:
    def __init__(self) -> None:
        self.commands: dict[str, str] = {}
        self.stopped = False

    async def open(self, name: str, command_id: str) -> bool:
        if self.stopped:
            return False
        self.commands.setdefault(command_id, name)
        return True

    def stop(self) -> None:
        self.stopped = True
