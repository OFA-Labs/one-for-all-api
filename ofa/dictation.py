"""Dictation flow (C4): enforce the user's exact words before anything is typed."""
from __future__ import annotations

import re

from .policy import Action
from .policy.lexicon import classify
from .text.dictation import find_span, verbatim
from .text.translit import apply_script

DICTATION_CUE = re.compile(r"\b(type|write|likho|likh do|likhna|dictate|enter the text|type karo)\b|लिखो|लिख दो|टाइप", re.I)


def paraphrases_dictation(action: Action, user_words: str) -> bool:
    """True when the user dictated but the engine tries to type different words through generic typing."""
    return bool(action.args.get("op") in {"type", "replace"} and action.payload and DICTATION_CUE.search(user_words)
                and find_span(user_words, action.payload) is None and not action.args.get("compose"))


async def prepare_dictation(action: Action, user_words: str, speak, listen, listen_dictation,
                            script: str) -> Action | dict:
    """Return the Action carrying the text to type, or a refusal result."""
    mode = action.args.get("mode", "verbatim")
    text = action.payload or ""
    if mode == "verbatim":
        span = find_span(user_words, text) if text else None
        if text and span is None:
            return {"status": "rejected", "reason": "VERBATIM_MISMATCH",
                    "detail": "text must be copied exactly from the user's words; omit text to ask the user to dictate"}
        if span is None:
            await speak("What should I type?")
            heard = await listen_dictation(45.0)
            if heard is None or not heard.text.strip():
                return {"status": "error", "reason": "NO_DICTATION"}
            span = heard.text
            if heard.confidence is not None and heard.confidence < 0.85 and re.search(r"\d|[A-Z][a-z]+", span):
                await speak(f"I heard: {span}. Is that right?")
                check = await listen(8.0)
                if check is None or classify(check.text) != "YES":
                    return {"status": "error", "reason": "DICTATION_NOT_CONFIRMED"}
        text = verbatim(apply_script(span, script))
    if not text.strip():
        return {"status": "error", "reason": "NOTHING_TO_TYPE"}
    await speak("Typing it now.")
    return action.model_copy(update={"payload": text})
