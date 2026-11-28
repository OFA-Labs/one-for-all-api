"""Append-only local record of what was dispatched, so a restart cannot repeat it.

Only identifiers, hashes and state names are written: never step text, URLs,
field values or error messages.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import ExecutionError, digest

_EVENT_PAYLOAD = {"reading_hash", "approve", "reason", "epoch", "code", "plan_hash"}


def default_dir(name: str, configured: str | None = None) -> str | None:
    """Launcher default. The config value "off" disables the ledger."""
    if configured:
        return None if configured.casefold() == "off" else configured
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return str(Path(base) / "OFA" / "execution-ledger" / name)


def effect_key(step, before) -> str:
    """Identity of one action across restarts: window handles, tab ids and refs change."""
    target = step.target.model_dump(exclude={"tab"})
    if any(target.get(k) for k in ("name", "path", "destination")):
        target.pop("ref")
    page = urlsplit(str(before.facts.get("url", "")))
    return digest({"operation": step.operation, "target": target, "text": step.text, "url": step.url,
                   "direction": step.direction, "origin": f"{page.scheme}://{page.netloc}"})


class Ledger:
    def __init__(self, root: str | Path, unknown_block_seconds: float = 86400):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.unknown_block_seconds = unknown_block_seconds
        self.events: deque = deque(maxlen=500)
        self.commands: dict[str, tuple[str, object]] = {}
        self._effects: dict[str, dict] = {}
        self._done: set[tuple[str, str]] = set()
        self._lock = threading.Lock()
        self._prev = "0" * 64
        self._load()

    def _load(self) -> None:
        files = sorted(self.root.glob("*.jsonl"))
        for path in files:
            raw = path.read_bytes()
            if path == files[-1] and raw and not raw.endswith(b"\n"):
                # A crash mid-append. The intent record is flushed before dispatch,
                # so a half-written line never stands for a sent action.
                raw = raw[:raw.rfind(b"\n") + 1]
                with path.open("r+b") as stream:
                    stream.truncate(len(raw))
            for line in raw.decode("utf-8", errors="replace").splitlines():
                try:
                    self._apply(json.loads(line))
                except (ValueError, KeyError, TypeError) as exc:
                    raise ExecutionError("LEDGER_CORRUPT",
                                         f"The execution ledger {path.name} is damaged; inspect it before continuing.") from exc
                self._prev = hashlib.sha256(line.encode()).hexdigest()

    def _apply(self, row: dict) -> None:
        if row["record"] == "effect":
            self._effects[row["key"]] = row
            if row["state"] == "verified":
                self._done.add((row["key"], row["step_id"]))
        elif row["record"] == "command":
            self.commands[row["command_id"]] = (row["hash"], row["result"])
        else:
            self.events.append(row["event"])

    def _append(self, row: dict) -> None:
        with self._lock:
            row = {**row, "ts": round(time.time(), 3), "prev": self._prev}
            line = json.dumps(row, sort_keys=True, ensure_ascii=False)
            try:
                with (self.root / (time.strftime("%Y-%m") + ".jsonl")).open("ab") as stream:
                    stream.write(line.encode() + b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            except OSError as exc:
                raise ExecutionError("LEDGER_UNAVAILABLE", "The execution ledger cannot be written.") from exc
            self._prev = hashlib.sha256(line.encode()).hexdigest()
            self._apply(row)

    def check(self, key: str, step_id: str) -> None:
        """Raise before an approval card is offered for an action that must not be sent again."""
        if (key, step_id) in self._done:
            raise ExecutionError("ALREADY_DONE", "This step was already carried out and verified.")
        last = self._effects.get(key)
        if last and last["state"] in {"intent", "unknown"} and time.time() - last["ts"] < self.unknown_block_seconds:
            raise ExecutionError("OUTCOME_UNKNOWN",
                                 "This action was sent earlier and its outcome is unknown. "
                                 "Check the application; it will not be sent again.")

    def effect(self, key: str, state: str, **ids) -> None:
        self._append({"record": "effect", "key": key, "state": state, **ids})

    def command(self, command_id: str, hashed: str, result: object) -> None:
        self._append({"record": "command", "command_id": command_id, "hash": hashed, "result": result})

    def event(self, event: dict) -> None:
        payload = {k: v for k, v in event["payload"].items() if k in _EVENT_PAYLOAD}
        if "evidence" in event["payload"]:
            payload["evidence"] = [{k: e[k] for k in ("tier", "kind", "reading_hash")}
                                   for e in event["payload"]["evidence"]]
        self._append({"record": "event", "event": {**event, "payload": payload}})
