"""Script normalization (§4.2): change script only, never words. Default Roman Hinglish."""
from __future__ import annotations

import re

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate

DEV = re.compile(r"[ऀ-ॿ]+")
CASUAL = [("aa", "aa"), ("ee", "ee"), ("oo", "oo"), ("~n", "n"), (".n", "n"), ("M", "n"), ("H", "h"), ("N", "n"),
          ("R", "r"), ("Sh", "sh"), ("sh", "sh"), ("chh", "chh"), ("A", "aa"), ("I", "ee"), ("U", "oo"),
          (".D", "d"), (".Dh", "dh"), ("x", "ksh"), ("GY", "gy"), ("T", "t"), ("D", "d"), ("j~", "gy")]


def has_devanagari(text: str) -> bool:
    return bool(DEV.search(text or ""))


def _roman_word(word: str) -> str:
    r = transliterate(word, sanscript.DEVANAGARI, sanscript.ITRANS)
    for a, b in CASUAL:
        r = r.replace(a, b)
    r = re.sub(r"a\b", "a", r)
    # common schwa deletion at word end ("haina" -> "hain", "karana" -> "karna" is out of scope)
    if len(r) > 3 and r.endswith("a") and not r.endswith("aa") and word[-1] not in "ाअ":
        r = r[:-1]
    return r.lower()


def to_roman(text: str) -> str:
    return DEV.sub(lambda m: _roman_word(m.group(0)), text).replace("।", ".")


def to_devanagari(text: str) -> str:
    return text      # Roman → Devanagari is lossy for Hinglish; kept as spoken (documented limitation)


def apply_script(text: str, pref: str = "roman") -> str:
    if pref == "roman":
        return to_roman(text)
    if pref == "devanagari":
        return to_devanagari(text)
    return text
