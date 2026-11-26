"""Small typed seams keep audio, providers and effectors independently testable."""
from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol

Emit = Callable[[str, dict[str, Any]], None]


@dataclass(frozen=True)
class Transcript:
    text: str
    final: bool
    confidence: float | None = None
    language: str | None = None


@dataclass(frozen=True)
class Audio:
    pcm: bytes
    rate: int = 24000


class ProviderError(Exception):
    def __init__(self, code: str, permanent: bool = False) -> None:
        super().__init__(code)
        self.code = code
        self.permanent = permanent


class SttProvider(Protocol):
    name: str

    def stream(self, frames: AsyncIterator[bytes]) -> AsyncIterator[Transcript]:
        raise NotImplementedError


class TtsProvider(Protocol):
    name: str
    voice: str

    def stream(self, text: str, language: str) -> AsyncIterator[Audio]:
        raise NotImplementedError


class LlmProvider(Protocol):
    def stream(self, text: str, language: str) -> AsyncIterator[str]:
        raise NotImplementedError


class ActionBridge(Protocol):
    async def open(self, name: str, command_id: str) -> bool:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError
