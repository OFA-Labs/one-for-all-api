"""OFA's eyes: see the screen, understand it, point the hands at the right thing.

    scene.py      read visible windows (accessibility, then OCR where text is missing), number every element
    capture.py    masked, numbered screenshot for a vision model
    providers.py  local | separate | reasoning (chosen in Settings → Eyes)
    attention.py  notices new pop-ups (an incoming call, a notification) so "pick it up" knows what "it" is

The Eyes subgraph (ofa/graphs/eyes.py) orders these steps and stops at the first confident answer.
"""
from __future__ import annotations

from ..settings_store import SettingsStore
from .providers import LocalEyes, ModelEyes, vision_engine


class Eyes:
    """Chooses the provider the user picked. The reasoning engine is only used, never changed."""

    def __init__(self, settings: SettingsStore, reasoning_engine):
        self.settings, self.reasoning_engine = settings, reasoning_engine
        self.local = LocalEyes()
        self._separate: dict[str, ModelEyes] = {}

    @property
    def mode(self) -> str:
        return self.settings.get().eyes.mode

    def reasoning_can_see(self) -> bool:
        try:
            return bool(self.reasoning_engine.info().supports_vision)
        except Exception:
            return False

    def provider(self):
        """The provider for the chosen mode; local when the chosen model cannot see."""
        eyes = self.settings.get().eyes
        if eyes.mode == "separate":
            if eyes.model not in self._separate:
                self._separate[eyes.model] = ModelEyes(vision_engine(eyes.model), "separate")
            return self._separate[eyes.model]
        if eyes.mode == "reasoning" and self.reasoning_can_see():
            return ModelEyes(self.reasoning_engine, "reasoning")
        return self.local

    def status(self) -> dict:
        eyes = self.settings.get().eyes
        provider = self.provider()
        return {"mode": eyes.mode, "model": eyes.model if eyes.mode == "separate" else None,
                "active": provider.name, "sees_images": provider.sees_images,
                "reasoning_can_see": self.reasoning_can_see(),
                "note": "The reasoning model cannot see images, so Eyes uses local reading."
                if eyes.mode == "reasoning" and not self.reasoning_can_see() else None}
