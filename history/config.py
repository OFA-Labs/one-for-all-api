"""History configuration: ``HISTORY_*`` environment variables (separate from ``EBRAIN_*``)."""
from __future__ import annotations

import os

DEFAULT_TZ = "Asia/Kolkata"
ROLES = ("member", "service")
MAX_BODY_BYTES = 256 * 1024


def default_data_dir() -> str:
    """Mirrors E-Brain: ``%LOCALAPPDATA%`` on Windows, the home directory elsewhere."""
    base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(base, "one-for-all", "history")


def _parse_tokens(raw: str) -> dict:
    """``{"token": {"user": "demo", "role": "member"}}``; anything invalid fails closed."""
    import json

    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    tokens: dict = {}
    for token, entry in data.items():
        if not isinstance(token, str) or not token or not isinstance(entry, dict):
            continue
        role = entry.get("role")
        user = entry.get("user")
        if role == "member" and isinstance(user, str) and user:
            tokens[token] = {"user": user, "role": "member"}
        elif role == "service":
            tokens[token] = {"user": None, "role": "service"}
    return tokens


def load_config(env: dict | None = None) -> dict:
    """Reads ``HISTORY_DATA_DIR``, ``HISTORY_TOKENS`` and ``HISTORY_CURSOR_SECRET``.

    An unset or invalid ``HISTORY_TOKENS`` yields no tokens, so every request is 401.
    """
    env = os.environ if env is None else env
    secret = env.get("HISTORY_CURSOR_SECRET") or None
    return {
        "data_dir": env.get("HISTORY_DATA_DIR") or default_data_dir(),
        "tokens": _parse_tokens(env.get("HISTORY_TOKENS", "")),
        "cursor_secret": secret.encode("utf-8") if secret else None,
        "default_tz": DEFAULT_TZ,
        "max_body_bytes": MAX_BODY_BYTES,
    }
