"""Bounded utterance replay with independent cursors for provider failover."""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from .contracts import ProviderError


class ReplayFeed:
    def __init__(self, max_bytes: int = 960000) -> None:
        self._frames: list[bytes] = []
        self._bytes = 0
        self._limit = max_bytes
        self._ended = False
        self._condition = asyncio.Condition()

    async def push(self, pcm: bytes) -> None:
        async with self._condition:
            if self._ended:
                return
            if self._bytes + len(pcm) > self._limit:
                self._ended = True
                self._condition.notify_all()
                raise ProviderError("UTTERANCE_TOO_LONG")
            self._frames.append(bytes(pcm))
            self._bytes += len(pcm)
            self._condition.notify_all()

    async def end(self) -> None:
        async with self._condition:
            self._ended = True
            self._condition.notify_all()

    async def read(self) -> AsyncIterator[bytes]:
        cursor = 0
        while True:
            async with self._condition:
                await self._condition.wait_for(
                    lambda: cursor < len(self._frames) or self._ended
                )
                if cursor == len(self._frames):
                    return
                frame = self._frames[cursor]
                cursor += 1
            yield frame

    @property
    def size(self) -> int:
        return self._bytes
