"""Whole-utterance yes/no classifier for English, Hindi (Devanagari) and Roman Hinglish.

Only a clear yes counts. Any negation wins. Conditionals, 'but', questions and bare
acknowledgements ('ok', 'hmm') are not approvals. Patterns are code/config, never model output.
"""
from __future__ import annotations

import re
import unicodedata

YES, NO, MODIFY, UNCLEAR = "YES", "NO", "MODIFY", "UNCLEAR"

NO_WORDS = {"no", "nope", "nah", "dont", "don't", "stop", "cancel", "wait", "never", "abort", "hold",
            "nahi", "nahin", "nai", "mat", "ruko", "ruk", "rukiye", "rehne", "mana",
            "नहीं", "नही", "मत", "रुको", "रुकिए", "रहने", "मना"}
NO_PHRASES = ["do not", "hold on", "not now", "rehne do", "रहने दो"]
MODIFY_WORDS = {"but", "however", "instead", "except", "change", "edit", "if", "unless", "first",
                "lekin", "par", "magar", "agar", "pehle", "badal", "badlo",
                "लेकिन", "पर", "मगर", "अगर", "पहले", "बदलो", "बल्कि"}
YES_STRONG = {"yes", "yeah", "yep", "yup", "sure", "confirm", "confirmed", "affirmative", "absolutely",
              "haan", "haa", "han", "haanji", "hanji", "bilkul", "jarur", "zaroor", "zarur",
              "हाँ", "हां", "हा", "हाँजी", "बिल्कुल", "ज़रूर", "जरूर"}
YES_PHRASES = ["go ahead", "do it", "send it", "post it", "submit it", "please do", "theek hai", "thik hai",
               "kar do", "kardo", "bhej do", "bhejdo", "haan bhejo", "haan karo", "chalo karo", "kar dijiye",
               "bhej dijiye", "ठीक है", "कर दो", "भेज दो", "कर दीजिए", "भेज दीजिए"]
YES_FILLER = {"yes", "yeah", "yep", "yup", "sure", "go", "ahead", "do", "it", "send", "post", "submit",
              "please", "ok", "okay", "confirm", "confirmed", "absolutely", "that", "right", "correct",
              "haan", "haa", "han", "ji", "haanji", "hanji", "bilkul", "theek", "thik", "hai", "kar", "karo",
              "kardo", "bhej", "bhejo", "bhejdo", "chalo", "dijiye", "jarur", "zaroor", "zarur",
              "हाँ", "हां", "हा", "जी", "बिल्कुल", "ठीक", "है", "कर", "दो", "भेज", "करो", "भेजो", "चलो",
              "दीजिए", "ज़रूर", "जरूर", "हाँजी"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().replace("’", "'")
    text = re.sub(r"[^\w\s'ऀ-ॿ?]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify(text: str, confidence: float | None = None, min_confidence: float = 0.80) -> str:
    norm = normalize(text)
    if not norm:
        return UNCLEAR
    words = norm.replace("?", " ? ").split()
    if any(w.strip("'") in NO_WORDS or w in NO_WORDS for w in words) or any(p in norm for p in NO_PHRASES):
        return NO
    if "?" in words or any(w in MODIFY_WORDS for w in words):
        return MODIFY
    if len(words) > 8:
        return UNCLEAR
    strong = any(w in YES_STRONG for w in words) or any(p in norm for p in YES_PHRASES)
    if strong and all(w in YES_FILLER for w in words):
        if confidence is not None and confidence < min_confidence:
            return UNCLEAR
        return YES
    return UNCLEAR
