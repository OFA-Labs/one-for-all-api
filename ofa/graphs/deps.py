"""What graph nodes may use. Built once per core; nodes reach the outside world only through these."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from ..audit import Audit
from ..harness.api import Harness
from ..memory import Memory
from ..policy import ApprovalStore, TurnLog
from ..ports import VoicePort
from ..vault.broker import Broker


@dataclass
class Deps:
    harness: Harness
    approvals: ApprovalStore
    turns: TurnLog
    audit: Audit
    memory: Memory
    broker: Broker | None
    engine: object                       # ofa.engine contract; used, never changed
    voice: VoicePort
    epoch: Callable[[], int]
    lang: Callable[[], str] = lambda: "en"
    name: Callable[[], str] = lambda: ""
    handles: Callable[[], list[str]] = lambda: []
    show: Callable[..., None] = lambda *_: None          # panel captions: thinking / acting / approval
    control: Callable[[str], str | None] | None = None   # pause/resume, set by a voice front end
    eyes: object = None                                  # ofa.eyes.Eyes
    attention: object = None                             # ofa.eyes.attention.Attention
    settings: object = None                              # ofa.settings_store.SettingsStore
    corpus: object = None                                # ofa.corpus.OpenCorpus ("Use without consent")
    history: list[dict] = field(default_factory=list)    # last turns, for follow-ups like "it"
    history_turns: int = 6

    def __post_init__(self) -> None:
        from ..config import data_dir
        from ..corpus import OpenCorpus
        from ..eyes import Eyes
        from ..eyes.attention import Attention
        from ..settings_store import SettingsStore
        self.settings = self.settings or SettingsStore(None)
        self.eyes = self.eyes or Eyes(self.settings, self.engine)
        self.attention = self.attention or Attention(self.harness, self.memory)
        self.corpus = self.corpus or OpenCorpus(data_dir() / "corpus" / "open")
