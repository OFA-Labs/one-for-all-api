"""Groq Stage-1 engine (§7.1) over the OpenAI-compatible streaming chat API.
Every request body passes the egress guard first. Failures are reported, never silently switched."""
from __future__ import annotations

import base64
import json
import time
from typing import AsyncIterator

import httpx

from .. import live_budget
from ..config import groq_key
from ..egress import EGRESS, LeakBlocked
from .base import (Clock, Done, EngineError, EngineInfo, EngineMetrics, HealthResult, RedactedImage, TextDelta,
                   ToolCall, Usage)

URL = "https://api.groq.com/openai/v1"
# Verified 2026-11-26: console.groq.com/docs/models, /docs/tool-use, /docs/vision
MODELS = {
    "openai/gpt-oss-120b": EngineInfo("groq", "openai/gpt-oss-120b", True, False, False, 131072, 65536),
    "openai/gpt-oss-20b": EngineInfo("groq", "openai/gpt-oss-20b", True, False, False, 131072, 65536),
    "qwen/qwen3.8-27b": EngineInfo("groq", "qwen/qwen3.8-27b", True, True, True, 131072, 16384),
}


class GroqEngine:
    def __init__(self, model: str = "openai/gpt-oss-120b", client: httpx.AsyncClient | None = None,
                 timeout: float = 30.0, max_tokens: int = 2048, temperature: float = 0.2, count_budget=True):
        self.model = model
        self._info = MODELS.get(model, EngineInfo("groq", model, True, False, False, 131072, 8192))
        self._client = client
        self.timeout, self.max_tokens, self.temperature = timeout, max_tokens, temperature
        self._metrics = EngineMetrics()
        self.count_budget = count_budget

    def info(self) -> EngineInfo:
        return self._info

    def metrics(self) -> EngineMetrics:
        return self._metrics

    base_url = URL
    budget_name = "groq"

    def _key(self):
        return groq_key()

    def _headers(self) -> dict:
        key = self._key()
        if key is None:
            raise RuntimeError("GROQ_API_KEY is not set")
        return {"Authorization": f"Bearer {key.get_secret_value()}", "Content-Type": "application/json"}

    def _client_or_new(self) -> httpx.AsyncClient:
        return self._client or httpx.AsyncClient(timeout=httpx.Timeout(self.timeout, connect=10))

    async def health(self) -> HealthResult:
        start = time.monotonic()
        try:
            if self.count_budget:
                live_budget.spend(self.budget_name)
            async with self._client_or_new() as c:
                r = await c.get(f"{self.base_url}/models", headers=self._headers())
            ok = r.status_code == 200 and any(m.get("id") == self.model for m in r.json().get("data", []))
            return HealthResult(ok, f"http {r.status_code}" + ("" if ok else "; model not listed"),
                                (time.monotonic() - start) * 1000)
        except Exception as exc:
            return HealthResult(False, type(exc).__name__)

    def _body(self, messages, tools, images) -> dict:
        msgs = [dict(m) for m in messages]
        if images:
            if not self._info.supports_vision:
                raise ValueError("NO_VISION")
            for i in range(len(msgs) - 1, -1, -1):
                if msgs[i]["role"] == "user":
                    parts = [{"type": "text", "text": msgs[i]["content"]}]
                    for img in images[:3]:
                        if not isinstance(img, RedactedImage):
                            raise TypeError("only redacted images")
                        parts.append({"type": "image_url", "image_url": {
                            "url": "data:image/png;base64," + base64.b64encode(img.png).decode()}})
                    msgs[i] = {"role": "user", "content": parts}
                    break
        body = {"model": self.model, "messages": msgs, "stream": True, "max_tokens": self.max_tokens,
                "temperature": self.temperature, "stream_options": {"include_usage": True}}
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
            if not self._info.parallel_tools:
                body["parallel_tool_calls"] = False
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"
        return body

    async def stream(self, messages: list[dict], tools: list[dict], *, images=()) -> AsyncIterator:
        clock = Clock()
        try:
            body = self._body(messages, tools, images)
        except ValueError:
            yield EngineError("NO_VISION", False, "This model cannot read images.")
            return
        try:
            EGRESS.guard(body, "llm")
        except LeakBlocked:
            self._metrics.errors += 1
            yield EngineError("LEAK_BLOCKED", False, "I blocked a request that contained a protected value.")
            return
        if self.count_budget:
            try:
                live_budget.spend(self.budget_name)
            except live_budget.BudgetExceeded:
                yield EngineError("BUDGET", False, "The development live-call budget for Groq is used up.")
                return
        calls: dict[int, dict] = {}
        usage, finish = Usage(), "stop"
        client = self._client_or_new()
        try:
            async with client.stream("POST", f"{self.base_url}/chat/completions", headers=self._headers(), json=body) as r:
                self._metrics.rate_limits = {k: v for k, v in r.headers.items() if k.startswith("x-ratelimit")}
                if r.status_code != 200:
                    await r.aread()
                    self._metrics.errors += 1
                    yield self._http_error(r)
                    return
                async for line in r.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    chunk = json.loads(data)
                    u = chunk.get("usage") or (chunk.get("x_groq") or {}).get("usage")
                    if u:
                        usage = Usage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
                    for choice in chunk.get("choices", []):
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            clock.mark_first()
                            yield TextDelta(delta["content"])
                        for tc in delta.get("tool_calls") or []:
                            clock.mark_first()
                            slot = calls.setdefault(tc.get("index", 0), {"id": "", "name": "", "args": ""})
                            slot["id"] = tc.get("id") or slot["id"]
                            fn = tc.get("function") or {}
                            slot["name"] += fn.get("name") or ""
                            slot["args"] += fn.get("arguments") or ""
                        if choice.get("finish_reason"):
                            finish = choice["finish_reason"]
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            self._metrics.errors += 1
            yield EngineError("ENGINE_DOWN", True, "I can't reach Groq right now (" + type(exc).__name__ + ").")
            return
        finally:
            if self._client is None:
                await client.aclose()
        for i in sorted(calls):
            c = calls[i]
            yield ToolCall(c["id"] or f"call_{i}", c["name"], c["args"] or "{}")
        final = clock.usage(usage.input_tokens, usage.output_tokens)
        self._metrics.record(final)
        yield Done(final, finish)

    def _http_error(self, r: httpx.Response) -> EngineError:
        if r.status_code == 429:
            retry = r.headers.get("retry-after")
            secs = float(retry) if retry and retry.replace(".", "").isdigit() else None
            return EngineError("RATE_LIMIT", True, "Groq is rate-limiting me" +
                               (f" for about {int(secs)} seconds." if secs else "."), secs)
        if r.status_code in (401, 403):
            return EngineError("AUTH", False, "The Groq key was rejected.")
        if r.status_code >= 500:
            return EngineError("ENGINE_DOWN", True, "Groq had a server error.")
        try:
            msg = r.json().get("error", {}).get("message", "")[:160]
        except Exception:
            msg = ""
        return EngineError("BAD_REQUEST", False, "Groq rejected the request. " + msg)


class OpenAICompatEngine(GroqEngine):
    """Stage-2 Mode B backend: any OpenAI-compatible chat API the user connects with their own key.
    Same contract, so orchestrator, policy and broker are unchanged (§7.1)."""

    def __init__(self, base_url: str, model: str, key_env: str = "OFA_ENGINE_KEY", vision: bool = False, **kw):
        super().__init__(model, **kw)
        self.base_url, self.key_env, self.budget_name = base_url.rstrip("/"), key_env, "groq"
        self._info = EngineInfo("openai-compatible", model, True, False, vision, 128000, 8192, stage="user")

    def _key(self):
        from ..config import secret
        return secret(self.key_env)
