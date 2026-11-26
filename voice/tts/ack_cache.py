"""Provider/voice/format-aware PCM cache; memory lookup has no I/O."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
from pathlib import Path

from ..contracts import TtsProvider
from ..language import speech_text


class AckCache:
    def __init__(self, tts: TtsProvider, cache_dir: Path, voice_id: str) -> None:
        self._tts = tts
        self._dir = cache_dir
        self._voice = voice_id
        self._mem: dict[tuple[str, int], bytes] = {}
        self.failures: list[tuple[str, int]] = []
        self.phrases = {
            "en": ("Okay, done.", "Done."),
            "hi": ("ठीक है, हो गया।", "हो गया।"),
            "hinglish": ("Ok, ho gaya.", "Done, ho gaya."),
        }

    def _path(self, lang: str, text: str) -> Path:
        identity = (
            self._tts.name, self._voice, lang, text,
            "pcm16le", 24000, 1, "normalization-v1",
        )
        key = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
        return self._dir / (key + ".pcm")

    @staticmethod
    def _write(path: Path, pcm: bytes) -> None:
        handle, name = tempfile.mkstemp(dir=path.parent, suffix=".partial")
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(pcm)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    async def warm(self) -> None:
        await asyncio.to_thread(self._dir.mkdir, parents=True, exist_ok=True)
        for lang, phrases in self.phrases.items():
            for variant, text in enumerate(phrases):
                try:
                    await self._warm_one(lang, variant, text)
                except Exception:
                    self.failures.append((lang, variant))

    async def _warm_one(self, lang: str, variant: int, text: str) -> None:
        path = self._path(lang, text)
        pcm = await asyncio.to_thread(path.read_bytes) if path.exists() else b""
        if not pcm or len(pcm) % 2:
            chunks: list[bytes] = []
            async with asyncio.timeout(6):
                async for audio in self._tts.stream(speech_text(text, lang), lang):
                    chunks.append(audio.pcm)
            pcm = b"".join(chunks)
            if not pcm or len(pcm) % 2:
                raise ValueError("Invalid cached PCM")
            await asyncio.to_thread(self._write, path, pcm)
        self._mem[(lang, variant)] = pcm

    def get(self, lang: str, variant: int = 0) -> bytes:
        return self._mem[(lang, variant % len(self.phrases[lang]))]
