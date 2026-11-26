"""Engine registry (§7). OFA_ENGINE=groq|fake. Mode A/B engines register here later (M12)."""
from __future__ import annotations

from .base import ReasoningEngine


def get_engine(name: str = "groq", model: str = "openai/gpt-oss-120b") -> ReasoningEngine:
    if name == "groq":
        from .groq import GroqEngine
        return GroqEngine(model)
    if name == "openai-compatible":
        import os
        from .groq import OpenAICompatEngine
        return OpenAICompatEngine(os.environ["OFA_ENGINE_URL"], os.getenv("OFA_ENGINE_MODEL", model),
                                  vision=os.getenv("OFA_ENGINE_VISION") == "1")
    if name == "fake":
        from .fake import FakeEngine
        return FakeEngine()
    raise ValueError(f"Unknown engine {name!r}")
