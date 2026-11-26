from __future__ import annotations

import asyncio
import time
from pathlib import Path

import pytest

from voice.fakes import FakeTts
from voice.intent import Router
from voice.language import language_of, speech_text
from voice.replay import ReplayFeed
from voice.state import Machine, State
from voice.tts.ack_cache import AckCache


@pytest.mark.parametrize("text", [
    "open WhatsApp", "WhatsApp kholo", "व्हाट्सऐप खोलो",
    "please open WhatsApp", "whats app open karo",
])
def test_exact_open_aliases(text: str) -> None:
    aliases = {alias: "WhatsApp" for alias in ["whatsapp", "whats app", "व्हाट्सऐप"]}
    result = Router(aliases).route(text)
    assert result.intent == "open_app"
    assert result.slots == {"app": "WhatsApp"}


@pytest.mark.parametrize("text", [
    "open WhatsAp", "open cmd.exe", "open WhatsApp and send a message",
    "open https://evil.example", "open WhatsApp; delete files",
])
def test_fuzzy_and_injection_never_launch(text: str) -> None:
    assert Router({"whatsapp": "WhatsApp"}).route(text).intent != "open_app"


@pytest.mark.parametrize("text,expected", [
    ("hello", "en"), ("नमस्ते", "hi"), ("WhatsApp kholo", "hinglish"),
])
def test_language(text: str, expected: str) -> None:
    assert language_of(text) == expected
    assert language_of(text, "hinglish") == "hinglish"


def test_normalization_keeps_display_separate() -> None:
    display = "Ok, ho gaya."
    assert speech_text(display, "hinglish") == "ओके, हो गया।"
    assert display == "Ok, ho gaya."


def test_state_lifecycle_and_epoch() -> None:
    machine = Machine()
    for state in (State.ARMED, State.LISTENING, State.THINKING,
                  State.SPEAKING, State.INTERRUPTED, State.LISTENING, State.IDLE):
        machine.transition(state)
    assert machine.state == State.IDLE
    assert machine.epoch == 2
    with pytest.raises(ValueError):
        machine.transition(State.SPEAKING)


def test_replay_independent_cursors_and_bound() -> None:
    async def run() -> None:
        feed = ReplayFeed(max_bytes=4)
        await feed.push(b"ab")
        await feed.push(b"cd")
        await feed.end()
        first = [chunk async for chunk in feed.read()]
        second = [chunk async for chunk in feed.read()]
        assert first == second == [b"ab", b"cd"]
        overflow = ReplayFeed(max_bytes=1)
        with pytest.raises(Exception, match="UTTERANCE_TOO_LONG"):
            await overflow.push(b"ab")
    asyncio.run(run())


def test_cache_restart_voice_and_lookup(tmp_path: Path) -> None:
    async def run() -> None:
        tts = FakeTts()
        cache = AckCache(tts, tmp_path, "voice-a")
        await cache.warm()
        before = time.perf_counter_ns()
        pcm = cache.get("en")
        elapsed = time.perf_counter_ns() - before
        assert pcm and elapsed < 1_000_000
        assert tts.calls == 6
        offline = FakeTts(fail=True)
        restarted = AckCache(offline, tmp_path, "voice-a")
        await restarted.warm()
        assert restarted.get("en") == pcm
        assert offline.calls == 0
        changed = AckCache(tts, tmp_path, "voice-b")
        assert changed._path("en", "Done.") != cache._path("en", "Done.")
    asyncio.run(run())
