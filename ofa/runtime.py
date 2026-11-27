"""Builds the OFA core: engine, policy, vault, harness and the LangGraph agent (ofa.graphs).
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
from .graphs import Runner
from .graphs.deps import Deps
from .harness.api import Harness
from .memory import Memory
from .ports import VoicePort
from .settings_store import SettingsStore
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
    deps: Deps
    runner: Runner
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
    settings = SettingsStore(root / "settings.json")
    if not settings.path.exists():
        settings.update({"voice": {"reply_language": cfg.reply_language}})
    deps = Deps(harness, approvals, turns, audit, memory, broker, engine, voice, lambda: epoch_ref[0],
                lang=lambda: settings.get().voice.reply_language,
                name=lambda: memory.get("preferred_name", cfg.preferred_name),
                handles=lambda: [m["handle"] for m in vault.list()] + [f"session:{s}" for s in memory.get("sessions", [])],
                show=show, settings=settings)
    # Saved progress lives on disk for real use; fake-engine runs (tests) keep it in memory.
    on_disk = cfg.engine != "fake" and cfg.checkpoints == "sqlite"
    runner = Runner(deps, root / "graphs.db" if on_disk else None)
    core = Core(cfg, harness, approvals, turns, audit, memory, vault, broker, engine, deps, runner,
                voice=voice, epoch_ref=epoch_ref)
    built["core"] = core
    approvals.on_event = lambda kind, req: core.event("approval_" + kind, spoken=req.spoken[:200])
    return core
