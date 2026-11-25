"""Pre-persistence gate: bound, normalize and sanitize before any durable store.

A rejected payload retains minimal metadata only (code + digest, never raw text).
The gate is mandatory and cannot be switched off by configuration. Injection
text is data and never becomes an action.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Final

from ..config import V3Config
from ..errors import RejectedContent, TooLarge
from ..contracts import digest_of

# Synthetic detection patterns. They match representative test credentials, not
# real personal data; no matched value is ever echoed.
_SECRET_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i:(password|secret|api[_-]?key|token)\s*[=:]\s*\S{8,})"),
)
_INJECTION_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"ignore (all |any )?(previous|prior|above) instructions", re.I),
    re.compile(r"from now on|disregard (all |any )?instructions", re.I),
    re.compile(r"system (prompt|notice|message)", re.I),
    re.compile(r"(send|forward|post|upload)\b.{0,80}(https?://|@)", re.I),
    re.compile(r"\|\s*(sh|bash|powershell|cmd)\b", re.I),
    re.compile(r"\[(human|admin|owner|system|user)\]|verified human|top authority|"
               r"override everything|highest authority", re.I),
)


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    sanitized: str
    digest: str
    flags: tuple[str, ...]
    reason: str = ""

    def minimal_metadata(self) -> dict[str, object]:
        return {
            "accepted": self.accepted,
            "digest": self.digest,
            "flags": list(self.flags),
            "reason": self.reason,
        }


def _scan(value: str) -> tuple[str, tuple[str, ...]]:
    flags: set[str] = set()
    out = value
    for pattern in _SECRET_PATTERNS:
        if pattern.search(out):
            flags.add("secret_detected")
            out = pattern.sub("[REDACTED]", out)
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(out):
            flags.add("injection_text_detected")
            out = pattern.sub("[INERT_TEXT]", out)
    if any(ord(c) < 32 and c not in "\n\r\t" for c in out):
        flags.add("control_characters_removed")
        out = "".join(c for c in out if ord(c) >= 32 or c in "\n\r\t")
    return out, tuple(sorted(flags))


def _walk(value: Any, depth: int, cfg: V3Config) -> Any:
    if depth > cfg.max_nesting:
        raise RejectedContent("payload nesting exceeds bound")
    if isinstance(value, str):
        clean, flags = _scan(value)
        return clean
    if isinstance(value, dict):
        if len(value) > 512:
            raise RejectedContent("too many object keys")
        return {str(k): _walk(v, depth + 1, cfg) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        if len(value) > 2048:
            raise RejectedContent("too many array elements")
        return [_walk(v, depth + 1, cfg) for v in value]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    raise RejectedContent(f"unsupported payload type: {type(value).__name__}")


def sanitize(payload: str | dict[str, Any], cfg: V3Config | None = None) -> GateResult:
    """Sanitize and bound a client payload. Never returns raw rejected content."""
    cfg = (cfg or V3Config()).validate()
    if isinstance(payload, str):
        if len(payload) > cfg.max_text_chars:
            raise TooLarge("text exceeds bound")
        try:
            clean, flags = _scan(payload.encode("utf-8").decode("utf-8"))
        except UnicodeError as exc:
            raise RejectedContent("payload is not valid UTF-8") from exc
        return GateResult(True, clean, digest_of({"text": payload}), flags)
    try:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise RejectedContent("payload is not serializable") from exc
    if len(encoded.encode("utf-8")) > cfg.max_bytes:
        raise TooLarge("payload exceeds byte bound")
    clean = _walk(payload, 0, cfg)
    return GateResult(True, json.dumps(clean, sort_keys=True, separators=(",", ":")),
                      digest_of({"json": encoded}), tuple())


def gate_or_raise(payload: str | dict[str, Any], cfg: V3Config | None = None) -> GateResult:
    result = sanitize(payload, cfg)
    if not result.accepted:
        raise RejectedContent(result.reason or "payload rejected")
    return result
