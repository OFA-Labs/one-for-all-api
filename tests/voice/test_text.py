from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from voice.language import blocked, system_prompt



def test_language_prompts_and_blocked_messages() -> None:
    for language in ("en", "hi", "hinglish"):
        prompt = system_prompt(language)
        assert "verified executor" in prompt
        message = blocked(language, "Slack", "offline", "connection")
        assert all(value in message for value in ("Slack", "offline", "connection"))
