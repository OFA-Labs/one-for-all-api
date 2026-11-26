"""Stable reasoning-engine contract (§7.1). New engines (Mode A/B) implement only this."""
from __future__ import annotations

import statistics
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Protocol, Union


@dataclass(frozen=True)
class EngineInfo:
    id: str
    model: str
    supports_tools: bool
    parallel_tools: bool
    supports_vision: bool
    context_limit: int
    max_output: int
    stage: Literal["dev", "user"] = "dev"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    ttft_ms: float = 0.0


@dataclass
class TextDelta:
    text: str


@dataclass
class ToolCall:
    id: str
    name: str
    args_json: str


@dataclass
class Done:
    usage: Usage
    finish_reason: str


@dataclass
class EngineError:
    code: str                    # RATE_LIMIT | ENGINE_DOWN | BAD_REQUEST | NO_VISION | AUTH | LEAK_BLOCKED
    retryable: bool
    user_message: str
    retry_after: float | None = None


EngineEvent = Union[TextDelta, ToolCall, Done, EngineError]


@dataclass
class HealthResult:
    ok: bool
    detail: str = ""
    latency_ms: float = 0.0


@dataclass(frozen=True)
class RedactedImage:
    """Only ofa.harness.redact constructs these; raw screenshots cannot reach an engine."""
    png: bytes
    note: str = ""
    _token: object = field(default=None, repr=False, compare=False)


@dataclass
class EngineMetrics:
    calls: int = 0
    errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latencies: list[float] = field(default_factory=list)
    ttfts: list[float] = field(default_factory=list)
    rate_limits: dict = field(default_factory=dict)

    def record(self, u: Usage) -> None:
        self.calls += 1
        self.input_tokens += u.input_tokens
        self.output_tokens += u.output_tokens
        self.latencies.append(u.latency_ms)
        self.ttfts.append(u.ttft_ms)

    def summary(self) -> dict:
        def p(xs, q):
            if not xs:
                return None
            xs = sorted(xs)
            return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1)
        return {"calls": self.calls, "errors": self.errors, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "latency_p50_ms": p(self.latencies, .5),
                "latency_p95_ms": p(self.latencies, .95), "ttft_p50_ms": p(self.ttfts, .5),
                "ttft_mean_ms": round(statistics.mean(self.ttfts), 1) if self.ttfts else None,
                "rate_limits": self.rate_limits}


class ReasoningEngine(Protocol):
    def info(self) -> EngineInfo: ...
    async def health(self) -> HealthResult: ...
    def stream(self, messages: list[dict], tools: list[dict], *,
               images: tuple[RedactedImage, ...] = ()) -> AsyncIterator[EngineEvent]: ...
    def metrics(self) -> EngineMetrics: ...


class Clock:
    def __init__(self):
        self.start = time.monotonic()
        self.first: float | None = None

    def mark_first(self):
        if self.first is None:
            self.first = time.monotonic()

    def usage(self, i=0, o=0) -> Usage:
        end = time.monotonic()
        return Usage(i, o, (end - self.start) * 1000, ((self.first or end) - self.start) * 1000)
