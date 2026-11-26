"""Bounded UI events and metadata-only JSON timing logs."""
from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any, TextIO
from uuid import uuid4


class Events:
    def __init__(self, mode: str, output: TextIO | None = None) -> None:
        self.mode = mode
        self.output = output or sys.stdout
        self.session = str(uuid4())
        self.sequence = 0
        self.epoch = 0
        self.utterance = ""
        self.latest: dict[str, Any] = {"state": "IDLE"}
        self.observers: set[asyncio.Queue[dict[str, Any]]] = set()

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        self.sequence += 1
        self.epoch = int(payload.get("epoch", self.epoch))
        self.utterance = str(payload.get("utterance_id", self.utterance))
        event = {
            "protocol": "ofa.voice.v1", "sequence": self.sequence,
            "session_id": self.session, "utterance_id": self.utterance,
            "epoch": self.epoch, "type": kind, "mode": self.mode,
            "monotonic_ns": time.monotonic_ns(), "payload": payload,
        }
        if kind == "state":
            self.latest = dict(payload)
        safe = {key: value for key, value in payload.items()
                if key in {"provider", "capability", "state", "code", "epoch", "measurement", "dac_time"}}
        print(json.dumps({**event, "payload": safe}), file=self.output, flush=True)
        for queue in tuple(self.observers):
            if queue.full():
                self.observers.discard(queue)
                queue.get_nowait()
                queue.put_nowait({"type": "disconnect", "payload": {}})
            else:
                queue.put_nowait(event)

    def snapshot(self) -> dict[str, Any]:
        return {
            "protocol": "ofa.voice.v1", "type": "snapshot",
            "session_id": self.session, "sequence": self.sequence,
            "epoch": self.epoch, "payload": self.latest,
        }
