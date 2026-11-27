"""Developer configuration. Key values are SecretStr and never logged or repr'd."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr

log = logging.getLogger("ofa.config")
_warned: set[str] = set()


def data_dir() -> Path:
    base = os.getenv("OFA_DATA_DIR") or os.path.join(os.getenv("LOCALAPPDATA", str(Path.home())), "OFA")
    path = Path(base)
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_env_file(path: str | None) -> None:
    if not path:
        return
    from dotenv import load_dotenv
    load_dotenv(path, override=False)


def _speech_store() -> dict:
    """Speech keys saved earlier by `python -m voice --save-speech-credentials` (DPAPI)."""
    try:
        from voice.protected_store import ProtectedStore
        p = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "OFA/voice/credentials.dat"
        return ProtectedStore(p).read() if p.exists() else {}
    except Exception:
        return {}


def secret(name: str, *fallbacks: str) -> SecretStr | None:
    value = os.getenv(name)
    if value:
        return SecretStr(value)
    for alt in fallbacks:
        value = os.getenv(alt)
        if value:
            if alt not in _warned:
                _warned.add(alt)
                log.warning("Using %s; the expected variable name is %s. Please rename it.", alt, name)
            return SecretStr(value)
    if name in ("DEEPGRAM_API_KEY", "GRADIUM_API_KEY"):
        stored = _speech_store().get(name)
        if stored:
            return SecretStr(stored)
    return None


def groq_key() -> SecretStr | None:
    return secret("GROQ_API_KEY", "GROQ_API_KRY")


@dataclass
class OfaConfig:
    engine: str = field(default_factory=lambda: os.getenv("OFA_ENGINE", "groq"))
    groq_model: str = field(default_factory=lambda: os.getenv("OFA_GROQ_MODEL", "openai/gpt-oss-120b"))
    vision: bool = field(default_factory=lambda: os.getenv("OFA_VISION", "off") == "on")
    fastpath: bool = field(default_factory=lambda: os.getenv("OFA_FASTPATH", "off") == "on")
    port: int = field(default_factory=lambda: int(os.getenv("OFA_PORT", "8768")))
    preferred_name: str = field(default_factory=lambda: os.getenv("OFA_PREFERRED_NAME", ""))
    reply_language: str = field(default_factory=lambda: os.getenv("OFA_REPLY_LANGUAGE", "en"))
    script: str = field(default_factory=lambda: os.getenv("OFA_SCRIPT", "roman"))
    checkpoints: str = field(default_factory=lambda: os.getenv("OFA_CHECKPOINTS", "sqlite"))   # sqlite | memory
    fake: bool = False

    def names_set(self) -> dict[str, bool]:
        return {n: secret(n, *alts) is not None for n, alts in
                (("GROQ_API_KEY", ("GROQ_API_KRY",)), ("DEEPGRAM_API_KEY", ()), ("GRADIUM_API_KEY", ()))}
