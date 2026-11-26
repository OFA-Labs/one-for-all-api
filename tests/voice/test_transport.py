from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from collections.abc import AsyncIterator
from typing import Any

from voice.config import Settings


class Socket:
    def __init__(self, incoming: list[Any]) -> None:
        self.incoming = incoming
        self.sent: list[Any] = []

    async def __aenter__(self) -> Socket:
        return self

    async def __aexit__(self, *args: Any) -> None:
        return None

    async def send(self, message: Any) -> None:
        self.sent.append(message)

    async def recv(self) -> Any:
        return self.incoming.pop(0)

    def __aiter__(self) -> Socket:
        return self

    async def __anext__(self) -> Any:
        await asyncio.sleep(0)
        if not self.incoming:
            raise StopAsyncIteration
        return self.incoming.pop(0)


def adapter(monkeypatch: Any, name: str, socket: Socket) -> Any:
    for module_name in ("websockets", "websockets.asyncio", "websockets.asyncio.client"):
        if module_name not in sys.modules:
            module = types.ModuleType(module_name)
            module.connect = lambda *args, **kwargs: socket
            monkeypatch.setitem(sys.modules, module_name, module)
    module = importlib.import_module("voice." + name)
    monkeypatch.setattr(module, "connect", lambda *args, **kwargs: socket)
    return module


async def frames() -> AsyncIterator[bytes]:
    yield bytes(960)


def test_deepgram_accumulates_final_segments(monkeypatch: Any) -> None:
    incoming = [json.dumps({
        "type": "Results", "is_final": True, "speech_final": finished,
        "channel": {"alternatives": [{"transcript": text, "confidence": 0.98}]},
    }) for text, finished in (("open", False), ("WhatsApp", True))]
    socket = Socket(incoming)
    module = adapter(monkeypatch, "deepgram", socket)

    async def run() -> None:
        results = [result async for result in module.DeepgramStt(Settings()).stream(frames())]
        assert [result.text for result in results if result.final] == ["open WhatsApp"]
        assert bytes(960) in socket.sent
    asyncio.run(run())


def test_flux_tts_uses_metadata_as_completion(monkeypatch: Any) -> None:
    socket = Socket([json.dumps({"type": "SpeechStarted"}), b"abcd",
                     json.dumps({"type": "SpeechMetadata"})])
    module = adapter(monkeypatch, "deepgram", socket)

    async def run() -> None:
        result = [audio.pcm async for audio in module.DeepgramTts(Settings()).stream("Done.", "en")]
        assert result == [b"abcd"]
        messages = [json.loads(message) for message in socket.sent]
        assert messages == [{"type": "Speak", "text": "Done."}, {"type": "Flush"}]
    asyncio.run(run())


def test_gradium_pcm24_and_terminal_transcript(monkeypatch: Any) -> None:
    socket = Socket([json.dumps({"type": "ready", "sample_rate": 24000}),
                     json.dumps({"type": "text", "text": "open WhatsApp"}),
                     json.dumps({"type": "end_of_stream"})])
    module = adapter(monkeypatch, "gradium", socket)

    async def run() -> None:
        results = [result async for result in module.GradiumStt(Settings()).stream(frames())]
        assert [result.text for result in results if result.final] == ["open WhatsApp"]
        assert results[-1].confidence is None
        messages = [json.loads(message) for message in socket.sent]
        assert messages[0]["input_format"] == "pcm"
        assert messages[-1] == {"type": "end_of_stream"}
    asyncio.run(run())
