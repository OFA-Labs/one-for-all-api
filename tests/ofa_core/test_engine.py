"""R1 contract, R3 KRY fallback, R4 errors surfaced (no switch), R5 egress on the wire, A14/H8 no bypass."""
import ast
import asyncio
import json
import logging
from pathlib import Path

import httpx
import pytest

from ofa.egress import EGRESS
from ofa.engine.base import Done, EngineError, RedactedImage, TextDelta, ToolCall
from ofa.engine.groq import GroqEngine, OpenAICompatEngine

SSE = "\n".join("data: " + json.dumps(c) for c in [
    {"choices": [{"delta": {"role": "assistant"}}]},
    {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_1", "function": {"name": "open", "arguments": ""}}]}}]},
    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "{\"target\":"}}]}}]},
    {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": "\"notepad\"}"}}]}, "finish_reason": "tool_calls"}]},
    {"choices": [], "x_groq": {"usage": {"prompt_tokens": 120, "completion_tokens": 30}}},
]) + "\ndata: [DONE]\n"


def engine(handler, monkeypatch, cls=GroqEngine, **kw):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_value_123456")
    monkeypatch.setenv("OFA_ENGINE_KEY", "sk_test_value_123456")
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    if cls is GroqEngine:
        return GroqEngine("openai/gpt-oss-120b", client=client, count_budget=False)
    return cls(client=client, count_budget=False, **kw)


def collect(e, msgs=None, images=()):
    async def run():
        return [ev async for ev in e.stream(msgs or [{"role": "user", "content": "open notepad"}],
                                            [{"type": "function", "function": {"name": "open"}}], images=images)]
    return asyncio.run(run())


def test_streamed_tool_call_parsed_with_usage_and_ratelimit_headers(monkeypatch):
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        seen["auth"] = req.headers["authorization"]
        return httpx.Response(200, text=SSE, headers={"x-ratelimit-limit-tokens": "8000"})
    e = engine(handler, monkeypatch)
    evs = collect(e)
    calls = [x for x in evs if isinstance(x, ToolCall)]
    assert calls[0].name == "open" and json.loads(calls[0].args_json) == {"target": "notepad"}
    assert isinstance(evs[-1], Done) and evs[-1].usage.input_tokens == 120
    assert seen["body"]["parallel_tool_calls"] is False and seen["body"]["stream"] is True
    assert e.metrics().summary()["rate_limits"]["x-ratelimit-limit-tokens"] == "8000"
    info = e.info()
    assert info.supports_tools and not info.supports_vision and info.context_limit == 131072


@pytest.mark.parametrize("code,expected", [(429, "RATE_LIMIT"), (401, "AUTH"), (503, "ENGINE_DOWN"), (400, "BAD_REQUEST")])
def test_http_errors_become_engine_errors(monkeypatch, code, expected):
    e = engine(lambda req: httpx.Response(code, json={"error": {"message": "x"}}, headers={"retry-after": "7"}), monkeypatch)
    evs = collect(e)
    assert isinstance(evs[0], EngineError) and evs[0].code == expected
    if code == 429:
        assert evs[0].retry_after == 7 and evs[0].retryable


def test_no_vision_model_refuses_images(monkeypatch):
    e = engine(lambda req: httpx.Response(200, text=SSE), monkeypatch)
    evs = collect(e, images=(RedactedImage(b"png"),))
    assert evs[0].code == "NO_VISION"


def test_secret_never_reaches_the_wire(monkeypatch):
    sent = []
    e = engine(lambda req: sent.append(req) or httpx.Response(200, text=SSE), monkeypatch)
    EGRESS.register("WireSecret-777")
    evs = collect(e, msgs=[{"role": "user", "content": "my password is WireSecret-777"}])
    assert evs[0].code == "LEAK_BLOCKED" and not sent
    EGRESS.forget_all()


def test_kry_fallback_warns_without_value(monkeypatch, caplog):
    import ofa.config as cfg
    cfg._warned.clear()
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KRY", "gsk_typo_value_999")
    with caplog.at_level(logging.WARNING):
        assert cfg.groq_key().get_secret_value() == "gsk_typo_value_999"
    assert "GROQ_API_KRY" in caplog.text and "gsk_typo_value_999" not in caplog.text
    monkeypatch.setenv("GROQ_API_KEY", "gsk_right")
    assert cfg.groq_key().get_secret_value() == "gsk_right"


def test_user_engine_plugs_into_same_contract(monkeypatch):
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, text=SSE)
    e = engine(handler, monkeypatch, cls=OpenAICompatEngine, base_url="https://api.example.ai/v1", model="m-1")
    evs = collect(e)
    assert seen["url"] == "https://api.example.ai/v1/chat/completions" and any(isinstance(x, ToolCall) for x in evs)
    assert e.info().stage == "user"


def _imports(path):
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out.add(("." * n.level) + (n.module or ""))
    return out


def test_no_bypass_import_rules():
    root = Path("ofa")
    for f in root.rglob("*.py"):
        mods = _imports(f)
        rel = f.relative_to(root).as_posix()
        if "httpx" in mods:
            assert rel.startswith("engine/"), f"{rel} talks HTTP outside the engine/egress path"
        if rel.startswith(("harness/", "speech/", "eyes/")) or rel in {"phone.py", "tools.py"}:
            assert not any("vault" in m for m in mods), f"{rel} must not reach the vault directly"
            assert not any(m.endswith("approval") for m in mods if not rel.startswith("speech/")), f"{rel} touches approvals"
        # the hands graph is the only path from a tool call to an effect, and the only consumer of a grant
        text = f.read_text(encoding="utf-8")
        if rel != "graphs/hands.py" and not rel.startswith("effects/"):
            assert "run_effect" not in text, f"{rel} runs effects outside hands"
        if rel not in {"graphs/hands.py", "policy/approval.py"}:
            assert "approvals.consume(" not in text, f"{rel} consumes an approval outside hands"
    # approvals are decided only from Heard objects delivered by the speech loop
    src = Path("ofa/policy/approval.py").read_text(encoding="utf-8")
    assert "def decide(self, req_id: str, heard: Heard" in src
