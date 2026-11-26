"""Verbatim dictation (C4). The typed text must be the user's own words: the engine may only point at
a span of the transcript; OFA copies that span exactly and applies spoken punctuation commands."""
from __future__ import annotations

import re
import unicodedata

PUNCT = [(r"\b(new paragraph|naya paragraph)\b", "\n\n"), (r"\b(new line|next line|nayi line|nai line)\b", "\n"),
         (r"\b(full stop|period|poorna viraam|purn viram)\b", "."), (r"\b(comma|alpviraam)\b", ","),
         (r"\b(question mark|prashn chinh|prashnvachak)\b", "?"), (r"\b(exclamation mark|exclamation point)\b", "!"),
         (r"\b(colon)\b", ":"), (r"\b(semicolon)\b", ";"), (r"\b(open bracket)\b", "("), (r"\b(close bracket)\b", ")"),
         (r"(पूर्ण विराम)", "।"), (r"(अल्पविराम)", ","), (r"(नई लाइन)", "\n"), (r"(प्रश्न चिह्न)", "?")]


def spoken_punctuation(text: str) -> str:
    """Convert explicit punctuation commands. Only standalone command words are converted."""
    out = text
    for pattern, mark in PUNCT:
        out = re.sub(r"\s*" + pattern + r"\s*", lambda m: mark + (" " if mark not in "\n(" else ""), out, flags=re.I)
    out = re.sub(r"[ \t]+([.,?!:;)।])", r"\1", out)
    out = re.sub(r"\(\s+", "(", out)
    return re.sub(r"[ \t]{2,}", " ", out).strip(" ")


def _tokens(s: str) -> list[str]:
    s = unicodedata.normalize("NFC", s).casefold()
    return re.findall(r"[\wऀ-ॿ']+", s)


def find_span(words: str, candidate: str) -> str | None:
    """Return the exact substring of `words` whose tokens equal `candidate`'s tokens (case/punct-insensitive)."""
    want = _tokens(candidate)
    if not want:
        return None
    spans = [(m.group(0).casefold(), m.start(), m.end()) for m in re.finditer(r"[\wऀ-ॿ']+",
                                                                         unicodedata.normalize("NFC", words))]
    n = len(want)
    for i in range(len(spans) - n + 1):
        if [s[0] for s in spans[i:i + n]] == want:
            start, end = spans[i][1], spans[i + n - 1][2]
            tail = re.match(r"[.!?,।]*", words[end:]).group(0)
            return unicodedata.normalize("NFC", words)[start:end + len(tail)]
    return None


def verbatim(span: str) -> str:
    return spoken_punctuation(span)
