"""OFA's own voice must never be accepted as a command or an approval (§4.2, §6)."""
from __future__ import annotations

import time
from collections import deque

from rapidfuzz import fuzz


class EchoGuard:
    """Flags transcripts that match what OFA itself said recently (speaker bleed, replays)."""

    def __init__(self, window: float = 30.0, threshold: int = 82):
        self.recent: deque[tuple[float, str]] = deque(maxlen=20)
        self.window, self.threshold = window, threshold

    def note(self, text: str) -> None:
        self.recent.append((time.monotonic(), text.casefold()))

    def is_echo(self, text: str) -> bool:
        heard = text.casefold().strip()
        if len(heard.split()) < 2:
            return False
        now = time.monotonic()
        return any(now - at <= self.window and len(heard) <= len(said) + 5
                   and fuzz.partial_ratio(heard, said) >= self.threshold for at, said in self.recent)
