"""Injectable server clocks. Client timestamps are metadata, never commit order."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class Clock(Protocol):
    def iso(self) -> str: ...

    def tick(self) -> int: ...


@dataclass(frozen=True)
class SystemClock:
    """Wall clock; recorded times are always UTC and server assigned."""

    def iso(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="microseconds")

    def tick(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000)


@dataclass
class FakeClock:
    """Deterministic clock for reproducible tests and bitemporal fixtures."""

    start: str = "2026-01-01T00:00:00.000000+00:00"
    _n: int = 0

    def iso(self) -> str:
        base = datetime.fromisoformat(self.start)
        value = base.timestamp() + self._n
        self._n += 1
        return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec="microseconds")

    def tick(self) -> int:
        return self._n


UTC_EPOCH = "1970-01-01T00:00:00.000000+00:00"
