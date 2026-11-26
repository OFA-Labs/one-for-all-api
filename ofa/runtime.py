"""Builds the OFA core: engine, policy, vault, harness, executor and orchestrator.
The voice front end attaches through ofa.ports (see ofa.companion)."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

from .audit import Audit
from .config import OfaConfig, data_dir
from .egress import EGRESS, install_log_filter
from .engine import get_engine
from .executor import Executor
from .harness.api import Harness
from .memory import Memory
from .orchestrator import Orchestrator
from .ports import VoicePort
from .policy import ApprovalStore, TurnLog
from .vault.broker import Broker
from .vault.pm import detect
from .vault.store import Vault
from .vault.unlock import AutoVerifier

log = logging.getLogger("ofa")

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
    voice: VoicePort = field(default_factory=VoicePort)
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
    built: dict = {}
    voice = VoicePort(lambda kind, **data: built["core"].event(kind, **data))

    def show(kind, action=None):
        if kind == "approval" and action is not None:
            caption = f"{action.verb.upper()}: {(action.payload or '')[:160]}" + \
                      (f" → {', '.join(action.destinations)}" if action.destinations else "")
            voice.display("awaiting_approval", caption)
        elif kind == "approval_done":
            voice.display("acting", "")
        elif kind in {"thinking", "acting"}:
            voice.display(kind, None)

    epoch_ref = [0]
    executor = Executor(harness, approvals, turns, audit, memory, broker, voice.speak, voice.listen,
                        lambda: epoch_ref[0], lang=lambda: cfg.reply_language, show=show,
                        listen_dictation=voice.listen_dictation, pause_gate=voice.pause_gate)
    handles = lambda: [m["handle"] for m in vault.list()] + [f"session:{s}" for s in memory.get("sessions", [])]
    orch = Orchestrator(engine, executor, memory, voice.speak, voice.listen, handles=handles,
                        lang=lambda: cfg.reply_language, name=lambda: memory.get("preferred_name", cfg.preferred_name),
                        show=show)
    core = Core(cfg, harness, approvals, turns, audit, memory, vault, broker, engine, executor, orch,
                voice=voice, epoch_ref=epoch_ref)
    built["core"] = core
    approvals.on_event = lambda kind, req: core.event("approval_" + kind, spoken=req.spoken[:200])
    return core
