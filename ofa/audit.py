"""Append-only, hash-chained, redacted local audit log (§8.7). Stores handle ids, never values."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

from .egress import EGRESS, LeakBlocked

_ALLOWED = {"ts", "epoch", "task", "step", "tier", "kind", "digest", "handle_ids", "result", "detail", "prev"}


class Audit:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._prev = self._last_hash()

    def _file(self) -> Path:
        return self.root / (time.strftime("%Y-%m") + ".jsonl")

    def _last_hash(self) -> str:
        files = sorted(self.root.glob("*.jsonl"))
        if not files:
            return "0" * 64
        lines = files[-1].read_text(encoding="utf-8").splitlines()
        return hashlib.sha256(lines[-1].encode()).hexdigest() if lines else "0" * 64

    def write(self, kind: str, **fields) -> dict:
        entry = {k: v for k, v in fields.items() if k in _ALLOWED}
        entry.update(ts=round(time.time(), 3), kind=kind)
        if "detail" in entry:
            entry["detail"] = str(entry["detail"])[:300]
        with self._lock:
            entry["prev"] = self._prev
            line = json.dumps(entry, sort_keys=True, ensure_ascii=False)
            try:
                EGRESS.guard(line, "audit")
            except LeakBlocked:
                entry = {"ts": entry["ts"], "kind": kind, "result": "redacted_leak_blocked", "prev": self._prev}
                line = json.dumps(entry, sort_keys=True)
            with self._file().open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            self._prev = hashlib.sha256(line.encode()).hexdigest()
        return entry

    def entries(self, last: int = 50) -> list[dict]:
        out: list[dict] = []
        for f in sorted(self.root.glob("*.jsonl")):
            out += [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x]
        return out[-last:]

    def verify_chain(self) -> bool:
        prev = None
        for f in sorted(self.root.glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                entry = json.loads(line)
                if prev is not None and entry.get("prev") != prev:
                    return False
                prev = hashlib.sha256(line.encode()).hexdigest()
        return True

    def purge(self, before_month: str) -> int:
        n = 0
        for f in sorted(self.root.glob("*.jsonl")):
            if f.stem < before_month:
                f.unlink()
                n += 1
        self._prev = self._last_hash()
        self.write("audit_purged", detail=f"files={n} before={before_month}")
        return n
