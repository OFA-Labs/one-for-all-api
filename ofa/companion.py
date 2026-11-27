"""OFA as the brain of the existing Windows companion (voice/): its panel, Caps Lock, pairing and web
pages stay as they are; this adapter connects its Session to the OFA graphs (ofa.graphs).

The Session keeps owning audio, the state machine and the panel. When a graph pauses with a question,
the runner calls speak() and listen() here; the next utterance the Session hears is delivered to that
listen(). OfaBrain itself makes no decisions.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time

from voice.state import State

from .policy.approval import Heard
from .runtime import Core
from .speech.controls import control_of
from .speech.echo import EchoGuard
from .text.translit import has_devanagari

log = logging.getLogger("ofa.companion")

COMMAND_SILENCE_MS = 700
DICTATION_SILENCE_MS = 2600
SPEECH_CHUNK = 280


def sentences(text: str, limit: int = SPEECH_CHUNK) -> list[str]:
    """Split long replies (spoken plans) so one provider request never runs past the playback timeout."""
    parts, current = [], ""
    for piece in re.split(r"(?<=[.?!।])\s+", text.strip()):
        if current and len(current) + len(piece) + 1 > limit:
            parts.append(current)
            current = piece
        else:
            current = f"{current} {piece}".strip()
    return [*parts, current] if current else parts


class OfaBrain:
    def __init__(self, core: Core, echo: EchoGuard | None = None):
        self.core = core
        self.echo = echo or EchoGuard()
        self.session = None
        self.busy = False
        self.dictating = False
        self.paused = asyncio.Event()
        self.paused.set()
        self._waiters: list[asyncio.Future] = []
        self._expecting = False                     # a question was asked while OFA keeps typing
        self._early: list[Heard] = []               # answers that arrived before listen() was called
        self._emit = lambda kind, payload: None
        self._caption = lambda state, text="": None

    # --- wiring ---------------------------------------------------------------------------------
    def attach(self, session, emit=None, caption=None) -> None:
        self.session = session
        self._emit = emit or session.emit
        if caption is not None:
            self._caption = caption
        self.core.voice.attach(speak=self.speak, listen=self.listen, listen_dictation=self.listen_dictation,
                               pause_gate=self.paused.wait, display=self.display, expect=self.expect)
        self.core.deps.control = self.apply_control
        self.core.deps.attention.start()              # notices call pop-ups even before Caps Lock is pressed

    @property
    def waiting(self) -> bool:
        """True while OFA expects a spoken answer (approval, question or dictation)."""
        return self._expecting or any(not f.done() for f in self._waiters)

    def expect(self) -> None:
        self._expecting = True

    @property
    def silence_ms(self) -> int:
        return DICTATION_SILENCE_MS if self.dictating else COMMAND_SILENCE_MS

    # --- session lifecycle (Caps Lock) ---------------------------------------------------------
    def new_epoch(self) -> None:
        """Start or kill: everything pending is invalid from here (C1 kill switch)."""
        self.core.epoch_ref[0] += 1
        self.core.approvals.set_epoch(self.core.epoch_ref[0])
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
        self._waiters.clear()
        self._expecting = False
        self._early.clear()
        self.paused.set()
        self.dictating = False

    # --- what the core calls ----------------------------------------------------------------------
    def display(self, state: str, caption: str | None = None) -> None:
        """Captions only: the panel keeps its own states and visuals."""
        if state == "awaiting_approval":
            self._caption("THINKING", f"Say yes or no: {caption or ''}")
        elif state == "acting" and caption:
            self._caption("THINKING", caption)

    async def speak(self, text: str) -> float:
        session = self.session
        if session is None or session.machine.state == State.IDLE or not text:
            return time.monotonic()
        self.echo.note(text)
        self._emit("question" if text.rstrip().endswith("?") else "reply", {"text": text})
        language = "hi" if has_devanagari(text) else "en"
        for part in sentences(text):
            if session.machine.state == State.LISTENING:
                session.state(State.THINKING)
            await session._say(part, language)
        if session.machine.state in {State.SPEAKING, State.THINKING}:
            session.state(State.LISTENING)        # the microphone stays open while OFA works (stop, answers)
        return time.monotonic()

    async def listen(self, timeout: float) -> Heard | None:
        session = self.session
        if session is None or session.machine.state == State.IDLE:
            return None
        if session.machine.state in {State.SPEAKING, State.THINKING}:
            session.state(State.LISTENING)
        self._expecting = False
        if self._early:
            return self._early.pop(0)
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            return await asyncio.wait_for(waiter, timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def listen_dictation(self, timeout: float) -> Heard | None:
        self.dictating = True
        try:
            return await self.listen(timeout)
        finally:
            self.dictating = False

    # --- what the session calls -------------------------------------------------------------------
    def heard(self, text: str, confidence: float | None, source: str, started: float) -> Heard:
        return Heard(text, confidence, source, source == "mic" and self.echo.is_echo(text), started)

    def deliver(self, heard: Heard) -> bool:
        """Hand an utterance to whatever OFA is waiting for. Echoes are dropped."""
        if heard.echo:
            return True
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(heard)
                return True
        if self._expecting:
            self._early.append(heard)
            return True
        return False

    @staticmethod
    def control_kind(text: str) -> str | None:
        return control_of(text)

    def control(self, text: str) -> str | None:
        """Apply pause/resume. Returns the reply to speak, or None for an ordinary request."""
        return self.apply_control(control_of(text))

    def apply_control(self, kind: str | None) -> str | None:
        if kind == "pause":
            self.paused.clear()
            return "Paused. Say continue when you're ready."
        if kind == "resume":
            self.paused.set()
            return "Continuing."
        return None

    async def turn(self, text: str, confidence: float | None = None) -> str:
        """Run one request through OFA and return the sentence to say."""
        self.busy = True
        self.paused.set()
        try:
            self.core.event("heard", text=text)
            if control_of(text) == "resume_task":
                result = await self.core.runner.resume_last()
                if result is None:
                    return "There is no stopped task to continue."
            else:
                result = await self.core.runner.handle(text, confidence)
            self.core.event("turn", status=result.status, spoken=result.spoken)
            return result.spoken
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception("OFA turn failed")
            return f"Sorry, something went wrong on my side: {type(exc).__name__}."
        finally:
            self.busy = False


def build_brain() -> OfaBrain | None:
    """The brain, when a reasoning key is configured; otherwise the companion runs as before."""
    from .config import OfaConfig, groq_key
    from .runtime import build_core
    cfg = OfaConfig()
    if cfg.engine == "groq" and groq_key() is None:
        return None
    return OfaBrain(build_core(cfg))
