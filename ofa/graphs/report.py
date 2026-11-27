"""The spoken report at the end of a task. "Completed" is said only when OFA's own evidence shows the effects."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from ..egress import EGRESS, LeakBlocked

TAIL = re.compile(r"(\s*(anything else( you need| i can help with)?\??|is there anything else\??|done\.?|finished\.?))+\s*$", re.I)
READ_ONLY_TOOLS = {"screen", "windows", "files", "read_file", "look"}


@dataclass
class TurnResult:
    spoken: str
    status: str = "done"          # done|partial|failed|blocked|answered|cancelled|error
    actions: list[dict] = field(default_factory=list)
    verified: bool = False

    def as_state(self) -> dict:
        return asdict(self)


def tidy(text: str) -> str:
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"(\s*\.\.\.)+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\?\.", "?", text)
    for phrase in ("Completed. Anything else?", "Ho gaya. Aur kuch?"):
        if text.endswith(phrase):
            head = TAIL.sub("", text[: -len(phrase)]).strip().rstrip(".?!")
            text = (head + ". " if head else "") + phrase
    return re.sub(r"\.\s*\.", ".", text).strip()


def completed(lang: str) -> str:
    return "Ho gaya. Aur kuch?" if lang == "hi" else "Completed. Anything else?"


def report(finished: list | None, spoken_parts: list[str], actions: list[dict], ledger: list[dict],
           lang: str = "en") -> TurnResult:
    if finished is None and any(a["tier"] and a["tier"] >= 1 for a in actions):
        finished = ["done", " ".join(spoken_parts)[-300:]]   # no finish call: judged by evidence below
    status, summary = finished or ("answered", " ".join(spoken_parts)[-400:])
    effects = [a for a in actions if a["tier"] and a["tier"] >= 1 and a["tool"] not in READ_ONLY_TOOLS]
    failed = [a for a in effects if a["status"] not in {"ok", "skipped", "rejected"}]
    unverified = [a for a in effects if a["status"] == "ok" and not a["verified"]]
    outbound = [a for a in actions if a.get("outcome")]
    if status == "done" and (failed or unverified):
        status = "partial"
    if ledger and any(entry["status"] != "done" for entry in ledger):
        ok = [entry["dest"] for entry in ledger if entry["status"] == "done"]
        bad = [f"{entry['dest']} ({entry['status']})" for entry in ledger if entry["status"] != "done"]
        summary = (summary + " " if summary else "") + (f"Done for {', '.join(ok)}. " if ok else "") + \
            f"Not completed: {', '.join(bad)}."
        status = "partial" if ok else "failed"
    verified = status == "done" and bool(effects or outbound or not actions)
    if status == "done" and effects:
        head = TAIL.sub("", summary or "").strip().rstrip(".?! ")
        spoken = (head + ". " if head else "") + completed(lang)
    elif status == "done":
        spoken = summary or " ".join(spoken_parts) or completed(lang)
    elif status == "answered":
        spoken = summary or "Okay."
    else:
        note = {"partial": "I could only partly finish.", "failed": "That didn't work.",
                "blocked": "I'm blocked."}.get(status, "")
        detail = summary or ("; ".join(f"{a['verb']} {a['status']}" for a in failed[:3]))
        if unverified and not failed:
            detail += " I couldn't confirm the result on screen."
        spoken = f"{note} {detail}".strip()
    try:
        EGRESS.guard(spoken, "tts")
    except LeakBlocked:
        spoken = "I blocked my reply because it contained a protected value."
    return TurnResult(tidy(spoken), status, actions, verified)
