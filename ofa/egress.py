"""Single outbound chokepoint with leak canaries (§8.4).

Every LLM payload, log line, transcript, audit entry, TTS input and screenshot upload passes
`guard()`. Fingerprints of every secret the broker loads or releases are held in memory only.
A hit raises LeakBlocked; the caller must not send.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import secrets
import threading
from typing import Any
from urllib.parse import quote, quote_plus


class LeakBlocked(RuntimeError):
    def __init__(self, sink: str):
        super().__init__(f"Blocked an outbound {sink} payload containing a protected value")
        self.sink = sink


def _variants(value: str) -> set[str]:
    raw = value.encode()
    out = {value, value.lower(), "".join(value.split()), quote(value, safe=""), quote_plus(value),
           base64.b64encode(raw).decode(), base64.urlsafe_b64encode(raw).decode(),
           base64.b64encode(raw).decode().rstrip("="), binascii.hexlify(raw).decode(), value[::-1],
           json.dumps(value)[1:-1]}
    return {v for v in out if len(v) >= 4}


class Egress:
    def __init__(self) -> None:
        self._needles: dict[str, str] = {}
        self._lock = threading.Lock()
        self.alerts: list[dict] = []
        self.on_alert = None

    def register(self, value: str, label: str = "secret") -> None:
        if not value or len(value) < 4:
            return
        with self._lock:
            for v in _variants(value):
                self._needles[v] = label

    def forget_all(self) -> None:
        with self._lock:
            self._needles.clear()

    def canary(self) -> str:
        value = "ofa-canary-" + secrets.token_hex(12)
        self.register(value, "canary")
        return value

    def scan(self, payload: Any) -> str | None:
        if isinstance(payload, (bytes, bytearray)):
            text = bytes(payload).decode("utf-8", "ignore")
        elif isinstance(payload, str):
            text = payload
        else:
            text = json.dumps(payload, ensure_ascii=False, default=str)
        lowered = text.lower()
        with self._lock:
            for needle, label in self._needles.items():
                if needle in text or needle.lower() in lowered:
                    return label
        return None

    def guard(self, payload: Any, sink: str):
        label = self.scan(payload)
        if label:
            self.alerts.append({"sink": sink, "label": label})
            if self.on_alert:
                try:
                    self.on_alert(sink)
                except Exception:
                    pass
            raise LeakBlocked(sink)
        return payload


EGRESS = Egress()


class RedactingFilter(logging.Filter):
    """Drops any log record whose rendered text contains a protected value."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return False
        if EGRESS.scan(message):
            record.msg, record.args = "[log line blocked: contained a protected value]", ()
            EGRESS.alerts.append({"sink": "log", "label": "secret"})
        return True


def install_log_filter() -> None:
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(RedactingFilter())
    for handler in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
