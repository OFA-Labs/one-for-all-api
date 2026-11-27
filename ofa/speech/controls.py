"""Spoken session controls (C1) handled without the engine."""
from __future__ import annotations

import re

CONTROLS = {
    "stop": {"stop", "cancel", "stop it", "cancel it", "cancel that", "never mind", "nevermind",
             "bas", "band karo", "rehne do", "बस", "रहने दो", "cancel karo"},
    # "wait" and "ruko" hold the running task; they never end the session.
    "pause": {"pause", "hold on", "wait", "ek minute", "ek second", "thoda ruko", "ruko", "ruk", "ruk jao", "रुको", "रुक"},
    "resume": {"resume", "continue", "go on", "carry on", "chalo", "aage badho", "continue karo"},
    # a task stopped earlier (Caps Lock, a restart) is saved by the graph checkpointer
    "resume_task": {"continue the last task", "resume the last task", "continue my last task",
                    "pichla kaam continue karo", "pichla kaam karo"},
}


def control_of(text: str) -> str | None:
    """The control a whole utterance expresses, or None when it is an ordinary request."""
    words = re.sub(r"[^\w\sऀ-ॿ]", "", text.casefold()).strip()
    for kind, phrases in CONTROLS.items():
        if words in phrases:
            return kind
    return None
