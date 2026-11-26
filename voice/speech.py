"""Sentence-level failover resumes only the sentence not fully played."""
from __future__ import annotations

import asyncio
import math
import struct
from collections.abc import Callable
from typing import Any

from .config import Settings
from .contracts import Emit, ProviderError, TtsProvider
from .language import speech_text


class Speech:
    def __init__(self, settings: Settings, providers: dict[str, TtsProvider],
                 breakers: dict[str, Any], emit: Emit) -> None:
        self.settings, self.providers = settings, providers
        self.breakers, self.emit = breakers, emit

    async def say(self, text: str, language: str, playback: Any,
                  started: Callable[[], None]) -> bool:
        marker=getattr(playback,"marker",None)
        for index,name in enumerate(self.settings.tts_order):
            breaker = self.breakers[name]
            if not breaker.allow():
                continue
            if name == "gradium" and language != "en":
                breaker.release_probe()
                self.emit("degraded", {"code": "LANGUAGE_DEGRADED", "text": text})
                continue
            epoch = playback.epoch
            iterator = self.providers[name].stream(speech_text(text, language), language)
            try:
                first = await asyncio.wait_for(
                    anext(iterator), timeout=self.settings.first_tts_seconds
                )
                if not first.pcm:
                    raise ProviderError("TTS_EMPTY")
                if first.rate != 24000:
                    raise ProviderError("TTS_FORMAT")
                started()
                if index and marker: playback.mark(*marker)
                self.emit("tts_first_byte", {"provider": name})
                if index: self.emit("fallback_first_audio", {"provider":name,"measurement":"provider_first_chunk"})
                await playback.write(first.pcm, epoch)
                async with asyncio.timeout(20):
                    async for chunk in iterator:
                        if chunk.rate != 24000:
                            raise ProviderError("TTS_FORMAT")
                        await playback.write(chunk.pcm, epoch)
                await playback.drained(epoch)
                breaker.success()
                self.emit("sentence_played", {"provider": name})
                return True
            except asyncio.CancelledError:
                breaker.release_probe()
                raise
            except Exception as exc:
                breaker.failure(exc)
                playback.interrupt()
                self.emit("provider_failed", {"provider": name, "capability": "tts"})
            finally:
                await iterator.aclose()
        self.emit("error", {"code": "TTS_DOWN", "text": text})
        await self.earcon(playback)
        return False

    @staticmethod
    async def earcon(playback: Any) -> None:
        values = [int(1200 * math.sin(2 * math.pi * 660 * n / 24000))
                  for n in range(1920)]
        pcm = struct.pack("<" + "h" * len(values), *values)
        try:
            epoch = playback.epoch
            await playback.write(pcm, epoch)
            await playback.drained(epoch)
        except Exception:
            return
