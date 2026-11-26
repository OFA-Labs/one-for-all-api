"""Load external YAML; secret fields must reference the process environment."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .config import Settings, configured_origins


class Handoff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    secrets: dict[str, str]
    llm: dict[str, str]
    voice: dict[str, Any]
    machine: dict[str, str]
    git: dict[str, str]
    apps: dict[str, list[dict[str, Any]]]
    orchestrator: dict[str, str]
    execution: dict[str, Any] = Field(default_factory=dict)


def secret_value(reference: str) -> str:
    match = re.fullmatch(r"\$\{([A-Z][A-Z0-9_]*)\}", reference)
    if not match:
        raise ValueError("Secrets must be environment references")
    return os.getenv(match.group(1), "")


def load_handoff(path: str) -> Handoff:
    source = Path(path).expanduser().resolve()
    if source.stat().st_size > 65536:
        raise ValueError("Handoff exceeds 64 KiB")
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    return Handoff.model_validate(payload)


def settings_from_handoff(handoff: Handoff, consent: bool = False) -> Settings:
    voice = handoff.voice
    voices = voice.get("voice_ids", {})
    return Settings(
        mode=os.getenv("VOICE_PROVIDER_MODE", "fake"), consent=consent,
        origins=tuple(handoff.execution.get("allowed_web_origins") or configured_origins()),
        port=int(os.getenv("OFA_COMPANION_PORT", "8767")),
        command_only=voice.get("command_only", True),
        headphones=voice.get("headphones", False),
        language=voice.get("language", "auto"),
        stt_order=(voice.get("stt_primary", "deepgram"), voice.get("stt_fallback", "gradium")),
        tts_order=(voice.get("tts_primary", "deepgram"), voice.get("tts_fallback", "gradium")),
        deepgram_key=SecretStr(secret_value(handoff.secrets["DEEPGRAM_API_KEY"])),
        gradium_key=SecretStr(secret_value(handoff.secrets["GRADIUM_API_KEY"])),
        llm_key=SecretStr(secret_value(handoff.secrets.get("LLM_API_KEY", "${LLM_API_KEY}"))),
        llm_model=handoff.llm.get("model_conversation") or "gpt-5.4-mini-2026-03-17",
        planning_model=handoff.llm.get("model_agentic") or "gpt-5.4",
        english_voice=voices.get("en") or "flux-haley-en",
        hindi_voice=voices.get("hi") or "flux-anjali-hi",
        gradium_voice=voices.get("gradium_en") or "Bla6SbVMczYnOhfK",
        idle_seconds=voice.get("session_idle_timeout_s", 8),
        input_device=voice.get("audio_input_device"),
        output_device=voice.get("audio_output_device"),
        input_rate=voice.get("input_sample_rate", 24000),
    )
