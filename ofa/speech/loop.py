"""Persistent voice session (C1, §4.2). Caps Lock toggles; silence and task completion never end it.
Every final transcript is either: echo (dropped), a voice control, an answer to a pending question or
approval, a correction of the running task, or a new task. OFA's own speech is never a command."""
from __future__ import annotations

import asyncio
import math
import re
import struct
import time
from collections import deque
from contextlib import suppress

from rapidfuzz import fuzz

from voice.failover import Breaker
from voice.replay import ReplayFeed

from ..policy.approval import Heard
from ..text.translit import has_devanagari

CONTROLS = {
    "stop": {"stop", "cancel", "stop it", "cancel it", "cancel that", "never mind", "nevermind", "ruko", "ruk jao",
             "bas", "band karo", "rehne do", "रुको", "बस", "रहने दो", "cancel karo"},
    "pause": {"pause", "hold on", "wait", "ek minute", "ek second", "thoda ruko"},
    "resume": {"resume", "continue", "go on", "carry on", "chalo", "aage badho", "continue karo"},
}


def rms(pcm: bytes) -> float:
    n = len(pcm) // 2
    if not n:
        return 0.0
    samples = struct.unpack("<" + "h" * n, pcm[: n * 2])
    return math.sqrt(sum(x * x for x in samples) / n)


class EchoGuard:
    """Drops transcripts that match what OFA itself said recently (speaker bleed, replays)."""

    def __init__(self, window: float = 30.0, threshold: int = 82):
        self.recent: deque[tuple[float, str]] = deque(maxlen=20)
        self.window, self.threshold = window, threshold
        self.tts_end = 0.0

    def note(self, text: str) -> None:
        self.recent.append((time.monotonic(), text.casefold()))

    def ended(self) -> float:
        self.tts_end = time.monotonic()
        return self.tts_end

    def is_echo(self, text: str) -> bool:
        t = text.casefold().strip()
        now = time.monotonic()
        if len(t) < 2:
            return False
        for at, said in self.recent:
            if now - at > self.window:
                continue
            if len(t.split()) >= 2 and (fuzz.partial_ratio(t, said) >= self.threshold and len(t) <= len(said) + 5):
                return True
        return False


def control_of(text: str) -> str | None:
    t = re.sub(r"[^\w\sऀ-ॿ]", "", text.casefold()).strip()
    for kind, words in CONTROLS.items():
        if t in words:
            return kind
    return None


class VoiceLoop:
    def __init__(self, settings, stt: dict, stt_order, speech, capture, playback, set_state, on_turn,
                 echo: EchoGuard | None = None, emit=lambda *_: None):
        self.settings, self.stt, self.stt_order = settings, stt, stt_order
        self.speech, self.capture, self.playback = speech, capture, playback
        self.set_state, self.on_turn, self.emit = set_state, on_turn, emit
        self.echo = echo or EchoGuard()
        self.breakers = {name: Breaker(settings.cooldown_seconds) for name in stt}
        self.active = False
        self.epoch = 0
        self.mode = "command"
        self.waiters: list[asyncio.Future] = []
        self._utterances: set[asyncio.Task] = set()   # strong refs so tasks are not garbage-collected
        self.turn: asyncio.Task | None = None
        self.listener: asyncio.Task | None = None
        self.paused = asyncio.Event()
        self.paused.set()
        self.speaking = False
        self.lang = "en"
        self.on_epoch = lambda e: None
        self.on_pause = lambda paused: None

    # --- session ------------------------------------------------------------------------------
    async def toggle(self) -> None:
        if self.active:
            await self.stop("caps_lock")
        else:
            await self.start()

    async def start(self) -> None:
        self.epoch += 1
        self.on_epoch(self.epoch)
        self.active = True
        self.playback.start()
        self.capture.start()
        self.set_state("listening", "Listening…", mic=True)
        self.listener = asyncio.create_task(self._listen())

    async def stop(self, reason: str = "stop") -> None:
        """Kill switch: invalidate approvals, cancel the running task, stop audio."""
        self.active = False
        self.epoch += 1
        self.on_epoch(self.epoch)
        self.playback.interrupt()
        for f in self.waiters:
            if not f.done():
                f.set_result(None)
        self.waiters.clear()
        for t in (self.turn, self.listener):
            if t and not t.done() and t is not asyncio.current_task():
                t.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await t
        self.capture.close()
        self.playback.close()
        self.set_state("idle", "", mic=False)
        self.emit("session_stopped", {"reason": reason})

    def cancel_task(self) -> None:
        self.epoch += 1
        self.on_epoch(self.epoch)
        self.playback.interrupt()
        for f in self.waiters:
            if not f.done():
                f.set_result(None)
        self.waiters.clear()
        if self.turn and not self.turn.done():
            self.turn.cancel()

    # --- speaking / listening (used by orchestrator & executor) -------------------------------
    async def speak(self, text: str) -> float:
        if not text or not self.active:
            return time.monotonic()
        lang = "hi" if has_devanagari(text) else "en"
        self.echo.note(text)
        self.speaking = True
        prev = "thinking" if self.turn and not self.turn.done() else "listening"
        self.set_state("speaking", text)
        try:
            await self.speech.say(text, lang, self.playback, lambda: None)
        finally:
            self.speaking = False
            end = self.echo.ended()
            if self.active:
                self.set_state(prev, None)
        return end

    async def listen(self, timeout: float) -> Heard | None:
        if not self.active:
            return None
        fut = asyncio.get_running_loop().create_future()
        self.waiters.append(fut)
        try:
            return await asyncio.wait_for(fut, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            if fut in self.waiters:
                self.waiters.remove(fut)

    async def listen_dictation(self, timeout: float) -> Heard | None:
        self.mode = "dictation"
        try:
            return await self.listen(timeout)
        finally:
            self.mode = "command"

    # --- capture → utterances -------------------------------------------------------------------
    async def _listen(self) -> None:
        pre: deque[bytes] = deque(maxlen=12)
        positives, quiet, feed, started = 0, 0, None, 0.0
        while self.active:
            try:
                pcm = await asyncio.wait_for(self.capture.read(), timeout=2)
            except asyncio.TimeoutError:
                continue
            except Exception:
                self.set_state("error", "Microphone stopped working")
                await self.stop("audio_error")
                return
            gated = self.speaking and not self.settings.headphones
            if gated:
                pre.clear()
                positives = 0
                continue
            voiced = rms(pcm) >= self.settings.rms_threshold
            pre.append(pcm)
            positives = positives + 1 if voiced else 0
            if feed is None and positives >= 3:
                if self.speaking:          # headphone barge-in
                    self.playback.interrupt()
                    self.emit("barge_in", {})
                feed = ReplayFeed(int(self.settings.max_utterance_seconds * 48000 * (3 if self.mode == "dictation" else 1)))
                started = time.monotonic() - 0.02 * len(pre)
                for chunk in pre:
                    await feed.push(chunk)
                quiet = 0
                utterance = asyncio.create_task(self._utterance(feed, started))
                self._utterances.add(utterance)
                utterance.add_done_callback(self._utterances.discard)
            elif feed is not None:
                await feed.push(pcm)
                quiet = 0 if voiced else quiet + 20
                limit = 2600 if self.mode == "dictation" else max(700, self.settings.silence_ms)
                if quiet >= limit:
                    await feed.end()
                    feed = None
                    pre.clear()

    async def _utterance(self, feed: ReplayFeed, started: float) -> None:
        text, conf = "", None
        for name in self.stt_order(self.lang, self.mode):
            b = self.breakers[name]
            if not b.allow():
                continue
            try:
                async for t in self.stt[name].stream(feed.read()):
                    if t.final:
                        text, conf = t.text, t.confidence
                b.success()
                break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                b.failure(exc)
                self.emit("provider_failed", {"provider": name, "capability": "stt"})
                continue
        if not text.strip():
            return
        heard = Heard(text.strip(), conf, "mic", self.echo.is_echo(text), started)
        await self.dispatch(heard)

    async def dispatch(self, heard: Heard) -> None:
        if heard.echo:
            self.emit("echo_dropped", {})
            return
        self.lang = "hi" if has_devanagari(heard.text) else self.lang if self.lang == "hi" else "en"
        kind = control_of(heard.text)
        if kind == "stop":
            self.cancel_task()
            self.set_state("listening", "Stopped.")
            await self.speak("Stopped.")
            return
        if kind == "pause":
            self.paused.clear()
            self.on_pause(True)
            await self.speak("Paused. Say continue when you're ready.")
            return
        if kind == "resume":
            self.paused.set()
            self.on_pause(False)
            await self.speak("Continuing.")
            return
        if self.waiters:
            fut = self.waiters.pop(0)
            if not fut.done():
                fut.set_result(heard)
            return
        if self.turn and not self.turn.done():
            self.cancel_task()               # correction: the newest instruction wins
            self.emit("correction", {})
        self.turn = asyncio.create_task(self._run_turn(heard))

    async def _run_turn(self, heard: Heard) -> None:
        self.set_state("thinking", heard.text)
        try:
            await self.on_turn(heard)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.set_state("error", f"Something went wrong ({type(exc).__name__})")
            await self.speak("Sorry, something went wrong on my side.")
        finally:
            if self.active and asyncio.current_task() is self.turn:
                self.set_state("listening", None)
