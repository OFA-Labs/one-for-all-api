"""Validated local voice configuration; never serialize secrets into events."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["fake", "live"] = "fake"
    command_only: bool = True
    consent: bool = False
    headphones: bool = False
    language: Literal["auto", "en", "hi", "hinglish"] = "auto"
    stt_order: tuple[str, str] = ("deepgram", "gradium")
    tts_order: tuple[str, str] = ("deepgram", "gradium")
    deepgram_key: SecretStr = SecretStr("")
    gradium_key: SecretStr = SecretStr("")
    llm_key: SecretStr = SecretStr("")
    deepgram_host: str = "api.deepgram.com"
    llm_model: str = "gpt-5.4-mini-2026-03-17"
    planning_model: str = "gpt-5.4"
    english_voice: str = "flux-haley-en"
    hindi_voice: str = "flux-anjali-hi"
    gradium_voice: str = "Bla6SbVMczYnOhfK"
    idle_seconds: float = Field(default=8, ge=2, le=120)
    max_utterance_seconds: float = Field(default=20, ge=2, le=30)
    silence_ms: int = Field(default=240, ge=160, le=1200)
    rms_threshold: float = Field(default=500, ge=50, le=10000)
    # Measured cold-network probes on the developer machine: STT first event
    # 3.08 s, TTS first audio 2.05 s. Avoid false failover on a healthy provider.
    first_stt_seconds: float = Field(default=4.5, ge=0.2, le=5)
    first_tts_seconds: float = Field(default=3.5, ge=0.2, le=5)
    cooldown_seconds: float = Field(default=30, ge=1, le=300)
    input_device: int | None = None
    output_device: int | None = None
    input_rate: Literal[24000, 48000] = 24000
    port: int = Field(default=8767, ge=1024, le=65535)
    cache_dir: Path = Path.home() / "AppData/Local/OFA/voice-cache"
    origins: tuple[str, ...] = ("http://127.0.0.1:3000",)

    @model_validator(mode="after")
    def validate_live(self) -> Settings:
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"https", "http"} or not parsed.hostname or
                    parsed.path or parsed.query or parsed.fragment or parsed.username or
                    parsed.password or "*" in origin or
                    parsed.scheme == "http" and parsed.hostname not in {"127.0.0.1", "localhost"}):
                raise ValueError("Use exact HTTPS website origins or explicit loopback development origins")
        for order in (self.stt_order, self.tts_order):
            if set(order) != {"deepgram", "gradium"}:
                raise ValueError("Provider order must contain each provider once")
        if self.deepgram_host not in {
            "api.deepgram.com", "api.us.deepgram.com",
            "api.eu.deepgram.com", "api.in.deepgram.com",
        }:
            raise ValueError("Unrecognized Deepgram TLS host")
        if self.mode == "live" and not self.deepgram_key.get_secret_value():
            raise ValueError("Set DEEPGRAM_API_KEY for live speech")
        return self

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            mode=os.getenv("VOICE_PROVIDER_MODE", "fake"),
            command_only=os.getenv("VOICE_COMMAND_ONLY", "true") == "true",
            consent=os.getenv("VOICE_MIC_CONSENT", "false") == "true",
            headphones=os.getenv("VOICE_HEADPHONES", "false") == "true",
            language=os.getenv("VOICE_LANGUAGE", "auto"),
            deepgram_key=SecretStr(os.getenv("DEEPGRAM_API_KEY", "")),
            gradium_key=SecretStr(os.getenv("GRADIUM_API_KEY", "")),
            llm_key=SecretStr(os.getenv("LLM_API_KEY", "")),
            deepgram_host=os.getenv("OFA_DEEPGRAM_HOST", "api.deepgram.com"),
            origins=configured_origins(),
            port=int(os.getenv("OFA_COMPANION_PORT", "8767")),
        )


def configured_origins() -> tuple[str, ...]:
    values = [os.getenv("OFA_DEV_ORIGIN", "http://127.0.0.1:3000"),
              os.getenv("OFA_STAGING_ORIGIN", ""), os.getenv("OFA_PRODUCTION_ORIGIN", "")]
    return tuple(dict.fromkeys(value.strip().rstrip("/") for value in values if value.strip()))
