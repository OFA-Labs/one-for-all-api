"""Deterministic proxy token counter (INTERFACE.md section 4).

This is a proxy, not a model tokenizer: every run of word characters is one
token and every other non-space character is one token.
"""
from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def count_tokens(s: str) -> int:
    """Return the proxy token count of ``s``."""
    return len(_TOKEN_RE.findall(s))
