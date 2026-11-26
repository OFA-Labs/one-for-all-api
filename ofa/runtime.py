"""Builds the OFA core (engine, policy, vault, harness, executor, orchestrator) and the voice runtime."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field

from .audit import Audit
from .config import OfaConfig, data_dir, secret
from .egress import EGRESS, install_log_filter
from .engine import get_engine
from .executor import Executor
from .harness.api import Harness
from .memory import Memory
from .orchestrator import Orchestrator
from .policy import ApprovalStore, TurnLog
from .vault.broker import Broker
from .vault.pm import detect
from .vault.store import Vault
from .vault.unlock import AutoVerifier

log = logging.getLogger("ofa")

# Routing from docs/bench/results-*.md (synthetic speech; see CAPABILITY_REALITY.md).
STT_ROUTES = {("en", "command"): ["flux", "gradium", "nova3"], ("en", "dictation"): ["flux", "gradium", "nova3"],
              ("hi", "command"): ["flux", "nova3"], ("hi", "dictation"): ["flux", "nova3"]}


def stt_order(lang: str, mode: str) -> list[str]:
    return STT_ROUTES.get(("hi" if lang in {"hi", "hinglish"} else "en", mode), ["flux", "nova3"])


@dataclass
class Core:
    cfg: OfaConfig
    harness: Harness
    approvals: ApprovalStore
    turns: TurnLog
    audit: Audit
    memory: Memory
    vault: Vault
    broker: Broker
    engine: object
    executor: Executor
    orchestrator: Orchestrator
    log: deque = field(default_factory=lambda: deque(maxlen=200))
    state: dict = field(default_factory=lambda: {"session": "off", "caption": "", "mic": False, "pending": None})
    speak_impl: object = None
    listen_impl: object = None
    epoch_ref: list = field(default_factory=lambda: [0])

    def event(self, kind: str, **data) -> None:
        try:
            EGRESS.guard(data, "ui_log")
        except Exception:
            data = {"redacted": True}
        self.log.append({"ts": round(time.time(), 2), "kind": kind, **data})


def build_core(cfg: OfaConfig | None = None, harness: Harness | None = None, engine=None, verifier=None) -> Core:
    cfg = cfg or OfaConfig()
    install_log_filter()
    root = data_dir()
    audit = Audit(root / "audit")
    memory = Memory(root / "memory.db")
    vault = Vault(root / "vault", verifier or AutoVerifier())
    broker = Broker(vault, detect(), audit)
    approvals = ApprovalStore()
    turns = TurnLog()
    harness = harness or Harness()
    engine = engine or get_engine(cfg.engine, cfg.groq_model)
    holder: dict = {}

    async def speak(text):
        fn = holder.get("speak")
        if fn is None:
            holder["core"].event("say", text=text)
            return time.monotonic()
        return await fn(text)

    async def listen(timeout):
        fn = holder.get("listen")
        return await fn(timeout) if fn else None

    def show(kind, action=None):
        core = holder["core"]
        if kind == "approval" and action is not None:
            core.state["pending"] = {"verb": action.verb, "payload": action.payload, "to": action.destinations,
                                     "files": action.file_names, "account": action.account}
            caption = f"{action.verb.upper()}: {(action.payload or '')[:160]}" + \
                      (f" → {', '.join(action.destinations)}" if action.destinations else "")
            if holder.get("orb"):
                holder["orb"]("awaiting_approval", caption)
        elif kind == "approval_done":
            core.state["pending"] = None
            if holder.get("orb"):
                holder["orb"]("acting", "")
        elif holder.get("orb") and kind in {"thinking", "acting"}:
            holder["orb"](kind, None)

    epoch_ref = [0]
    executor = Executor(harness, approvals, turns, audit, memory, broker, speak, listen, lambda: epoch_ref[0],
                        lang=lambda: cfg.reply_language, show=show)
    handles = lambda: [m["handle"] for m in vault.list()] + [f"session:{s}" for s in memory.get("sessions", [])]
    orch = Orchestrator(engine, executor, memory, speak, listen, handles=handles, lang=lambda: cfg.reply_language,
                        name=lambda: memory.get("preferred_name", cfg.preferred_name), show=show)
    core = Core(cfg, harness, approvals, turns, audit, memory, vault, broker, engine, executor, orch,
                epoch_ref=epoch_ref)
    holder["core"] = core
    core._holder = holder
    approvals.on_event = lambda kind, req: core.event("approval_" + kind, spoken=req.spoken[:200])
    return core


def build_voice(core: Core, orb_set):
    """Real audio + providers. Returns a VoiceLoop bound to the core."""
    from voice.audio import Capture, Playback
    from voice.config import Settings
    from voice.deepgram import DeepgramStt, DeepgramTts
    from voice.failover import Breaker
    from voice.gradium import GradiumStt, GradiumTts
    from voice.speech import Speech

    from .speech.flux import FluxStt
    from .speech.loop import VoiceLoop

    dg, gr = secret("DEEPGRAM_API_KEY"), secret("GRADIUM_API_KEY")
    if dg is None:
        raise RuntimeError("DEEPGRAM_API_KEY is required for live voice (Hindi needs Deepgram)")
    s = Settings(mode="live", consent=True, deepgram_key=dg.get_secret_value(),
                 gradium_key=gr.get_secret_value() if gr else "",
                 headphones=os.getenv("OFA_HEADPHONES", "false") == "true", command_only=False, silence_ms=700,
                 tts_order=("gradium", "deepgram") if os.getenv("OFA_EN_TTS", "deepgram") == "gradium" else ("deepgram", "gradium"))
    stt = {"flux": FluxStt(dg.get_secret_value()), "nova3": DeepgramStt(s)}
    if gr:
        stt["gradium"] = GradiumStt(s)
    tts = {"deepgram": DeepgramTts(s), "gradium": GradiumTts(s)}
    breakers = {n: Breaker(s.cooldown_seconds) for n in tts}
    speech = Speech(s, tts, breakers, lambda k, d: core.event(k, **{x: y for x, y in d.items() if x != "text"}))

    def set_state(state, caption=None, mic=None):
        core.state["session"] = state
        if caption is not None:
            core.state["caption"] = caption
        if mic is not None:
            core.state["mic"] = mic
        orb_set(state, caption, mic)

    async def on_turn(heard):
        core.event("heard", text=heard.text)
        res = await core.orchestrator.handle(heard.text, heard.confidence)
        core.event("turn", status=res.status, spoken=res.spoken)
        if res.spoken:
            await loop.speak(res.spoken)

    loop = VoiceLoop(s, stt, lambda lang, mode: [n for n in stt_order(lang, mode) if n in stt], speech,
                     Capture(s.input_device, s.input_rate), Playback(s.output_device), set_state, on_turn,
                     emit=lambda k, d: core.event(k, **d))

    def on_epoch(e):
        core.epoch_ref[0] = e
        core.approvals.set_epoch(e)
    loop.on_epoch = on_epoch
    core._holder["speak"] = loop.speak
    core._holder["listen"] = loop.listen
    core._holder["orb"] = lambda st, cap: set_state(st, cap)
    core.executor._listen_dictation = loop.listen_dictation
    core.executor.gate = loop.paused.wait
    return loop
