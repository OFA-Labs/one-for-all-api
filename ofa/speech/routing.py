"""Speech-to-text routing by language and mode, from the voice benchmark (synthetic speech, 2026-11-26)."""
from __future__ import annotations

DEFAULT_ROUTE = ["flux", "nova3"]
STT_ROUTES = {("en", "command"): ["flux", "gradium", "nova3"], ("en", "dictation"): ["flux", "gradium", "nova3"],
              ("hi", "command"): ["flux", "nova3"], ("hi", "dictation"): ["flux", "nova3"]}


def stt_order(lang: str, mode: str) -> list[str]:
    return STT_ROUTES.get(("hi" if lang in {"hi", "hinglish"} else "en", mode), DEFAULT_ROUTE)
