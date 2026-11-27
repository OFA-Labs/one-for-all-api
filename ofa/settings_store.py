"""User settings for Eyes, Hands and Voice, edited from the web Settings page. Stored as JSON under data_dir()."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EyesMode = Literal["local", "separate", "reasoning"]


class EyesSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: EyesMode = Field(default_factory=lambda: os.getenv("OFA_EYES_MODE", "local"))
    model: str = Field(default_factory=lambda: os.getenv("OFA_EYES_MODEL", "qwen/qwen3.8-27b"),
                       pattern=r"^[\w./:-]{1,80}$")
    whole_screen: bool = True            # read every visible window, not only the front one


class HandsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system_controls: bool = True         # volume, brightness, media, lock, clipboard, Wi-Fi/Bluetooth pages
    answer_calls: bool = True            # "pick it up" answers a call pop-up without a second yes


class VoiceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply_language: Literal["en", "hi", "hinglish"] = "en"


class OfaSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    eyes: EyesSettings = Field(default_factory=EyesSettings)
    hands: HandsSettings = Field(default_factory=HandsSettings)
    voice: VoiceSettings = Field(default_factory=VoiceSettings)


class SettingsStore:
    def __init__(self, path: Path | None):
        """path=None keeps settings in memory only (tests, typed tools)."""
        self.path = path
        self._lock = threading.Lock()
        self._cached: OfaSettings | None = None

    def get(self) -> OfaSettings:
        with self._lock:
            if self._cached is None:
                try:
                    self._cached = OfaSettings.model_validate_json(self.path.read_text(encoding="utf-8"))
                except (AttributeError, OSError, ValueError):
                    self._cached = OfaSettings()
            return self._cached

    def update(self, patch: dict) -> OfaSettings:
        """Merge a partial update section by section; invalid values raise pydantic.ValidationError."""
        current = self.get().model_dump()
        for section, values in patch.items():
            if section not in current or not isinstance(values, dict):
                raise ValueError(f"unknown settings section {section!r}")
            current[section].update(values)
        updated = OfaSettings.model_validate(current)
        with self._lock:
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(updated.model_dump(), indent=1), encoding="utf-8")
                tmp.replace(self.path)
            self._cached = updated
        return updated
