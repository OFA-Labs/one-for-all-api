"""Hard caps on live provider calls (plan 00-INDEX). Counts persist in docs/bench/live-calls.json."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

CAPS = {"groq": 900, "deepgram": 600, "gradium": 300}
_lock = threading.Lock()


class BudgetExceeded(RuntimeError):
    pass


def _path() -> Path:
    default = Path(__file__).resolve().parents[2] / "docs" / "bench"
    p = Path(os.getenv("OFA_BENCH_DIR", str(default))) / "live-calls.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def used() -> dict[str, int]:
    p = _path()
    return json.loads(p.read_text()) if p.exists() else {}


def spend(provider: str, n: int = 1) -> int:
    with _lock:
        counts = used()
        total = counts.get(provider, 0) + n
        if total > CAPS.get(provider, 0):
            raise BudgetExceeded(f"{provider} live-call cap {CAPS.get(provider)} reached")
        counts[provider] = total
        _path().write_text(json.dumps(counts, indent=1))
        return total
