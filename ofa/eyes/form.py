"""Reads one page of a web form: every question with its input, including questions scrolled out of view.

The browser's accessibility tree lists elements in document order. Question text comes before its input, so
texts are collected until an input appears and become that input's question. Consecutive radio buttons or
check boxes form one question. Works for any form without a site-specific adapter (Google Forms, Microsoft
Forms, plain HTML); OFA's eyes take over only when a page exposes no inputs at all.
"""
from __future__ import annotations

import re
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import urlsplit

from ..harness.api import BROWSERS, Harness, HarnessError, Snapshot, norm

PAGE = re.compile(r"\bpage\s+(\d+)\s+of\s+(\d+)\b", re.I)
ERROR = re.compile(r"(this (is a )?required (question|field)|this question is required|please (enter|fill|answer|select)|"
                   r"enter a valid|must be|invalid|is required)", re.I)
CLOSED = re.compile(r"(no longer accepting responses|form is closed|this form is no longer|deadline has passed)", re.I)
DONE = re.compile(r"(your response has been recorded|thanks for (your )?(response|submitting)|response (was )?submitted|"
                  r"thank you for (your )?submission)", re.I)
# Address of a confirmation page, e.g. Google Forms' /formResponse.
CONFIRM_URL = re.compile(r"(formresponse|thank[-_]?you|thanks|success|confirm|submitted|complete)", re.I)
DECLARE = re.compile(r"\b(i (hereby )?(declare|confirm|certify|agree|accept|acknowledge|consent)|terms and conditions)", re.I)
SENSITIVE = re.compile(r"\b(password|passcode|otp|one[- ]time|pin\b|cvv|card number|bank account|ifsc|aadhaa?r|pan( card)?\b|"
                       r"passport number|social security|ssn)\b", re.I)
GENERIC = {"", "enter your answer", "your answer", "short answer text", "long answer text", "type here", "answer",
           "choose", "select", "select your answer"}
NAV = {"next": "next", "continue": "next", "back": "back", "previous": "back", "submit": "submit",
       "submit form": "submit", "send": "submit"}
INPUTS = {"edit", "combo box", "radio button", "check box"}
READ_ATTEMPTS = 6            # about 7 s: a browser that has just opened the page is still building its tree


@dataclass
class Option:
    id: str
    label: str
    checked: bool = False


@dataclass
class Field:
    id: str                      # element id to act on (for radio / check groups: the first option)
    question: str
    kind: str                    # text | long | select | radio | check | declare | file
    required: bool = False
    help: str = ""
    value: str = ""
    options: list[Option] = field(default_factory=list)
    error: str = ""
    sensitive: bool = False

    def key(self) -> str:
        return norm(self.question)[:120] or self.id

    def public(self) -> dict:
        data = {"id": self.id, "question": self.question, "kind": self.kind, "required": self.required}
        for name in ("help", "value", "error"):
            if getattr(self, name):
                data[name] = getattr(self, name)[:300]
        if self.options:
            data["options"] = [o.label for o in self.options]
        if self.sensitive:
            data["sensitive"] = True
        return data


@dataclass
class FormPage:
    hwnd: int
    title: str
    url: str | None
    fields: list[Field]
    nav: dict[str, str]          # next | back | submit -> element id
    page: tuple[int, int] | None  # (current, total) when the form shows a counter
    errors: list[str]
    closed: bool
    done: bool

    def signature(self) -> str:
        """Changes when OFA moved to another page."""
        return f"{self.page}|" + "|".join(f.key() for f in self.fields)

    def summary(self) -> dict:
        return {"page": self.page, "fields": len(self.fields), "nav": sorted(self.nav), "errors": self.errors[:5],
                "closed": self.closed, "done": self.done}

    def as_state(self) -> dict:
        return asdict(self)


def submission_readback(submitted_url: str | None, page: FormPage) -> str | None:
    """What a fresh reading proves after Submit was pressed.

    "verified": the form is gone and the browser moved to a different address that is a confirmation page, or
    that also says the response was recorded. "inferred": only the wording says so, which any page can print.
    None: nothing shows it.
    """
    gone = not page.fields and not page.nav and not page.errors
    if gone and submitted_url and page.url and page.url != submitted_url:
        moved = urlsplit(page.url)
        if page.done or CONFIRM_URL.search(f"{moved.path}#{moved.fragment}"):
            return "verified"
    return "inferred" if page.done else None


def _browser_window(h: Harness, window) -> dict:
    if window:
        return h.resolve_window(window)
    fg = h.b.foreground()
    wins = [w for w in h.b.list_windows() if w["process"] in BROWSERS and not w["minimized"]]
    if not wins:
        raise HarnessError("NO_BROWSER", "No browser window with a form is open")
    wins.sort(key=lambda w: w["hwnd"] != fg)
    return wins[0]


def _document(els: list, title: str) -> list:
    """Only the active page's elements: from its document node to the next document (another tab or pop-up)."""
    wanted = norm(title.replace("\u200b", ""))
    start = next((i for i, e in enumerate(els) if e.role == "document" and e.text
                  and wanted.startswith(norm(e.text)[:40])), None)
    if start is None:
        return []          # the page is not ready: never mistake the browser's own bars for a form
    rest = els[start + 1:]
    end = next((i for i, e in enumerate(rest) if e.role == "document"), len(rest))
    return rest[:end]


def read_form(h: Harness, window=None) -> FormPage:
    w = _browser_window(h, window)
    for attempt in range(READ_ATTEMPTS):
        # A browser builds its page accessibility tree only after the first request: read again if it is empty.
        els, _ = h.b.uia_tree(w["hwnd"], max_nodes=5000, budget_s=4.0, offscreen=True)
        if any(e.role in INPUTS or (e.role == "button" and norm(e.text) in NAV) for e in _document(els, w["title"])):
            break
        time.sleep(0.5 + 0.3 * attempt)
    url = (h.browser_identity(w["hwnd"]) or {}).get("url")
    doc = _document(els, w["title"])
    fields: list[Field] = []
    nav: dict[str, str] = {}
    texts: list[str] = []
    errors: list[str] = []
    page, closed, done = None, False, False
    group_open = False                        # radio / check options keep joining the last field
    group_name = ""                           # a radio group's own label (aria-labelledby), when the page sets one
    for e in doc:
        name = (e.text or "").strip()
        role = e.role
        if role == "button" and norm(name) in NAV:
            nav.setdefault(NAV[norm(name)], e.id)
            group_open = False
            continue
        if role in {"text", "heading", "group", "list item"} and name and role not in INPUTS:
            if PAGE.search(name) and len(name) < 40:
                found = PAGE.search(name)
                page = (int(found.group(1)), int(found.group(2)))
                continue
            if role == "group":
                group_name = name if len(name) < 300 else ""
                continue
            closed = closed or bool(CLOSED.search(name))
            done = done or bool(DONE.search(name))
            if ERROR.search(name) and len(name) < 120:
                errors.append(name)
                if fields and not fields[-1].error:
                    fields[-1].error = name
                continue
            if group_open and fields and any(norm(o.label) == norm(name) for o in fields[-1].options):
                continue                      # an option's own label repeated as text
            if role in {"text", "heading"} and name != "*":
                texts.append(name)
                group_open = False
            elif name == "*" and texts:
                texts[-1] += " *"
            continue
        if role not in INPUTS:
            continue
        if role in {"radio button", "check box"}:
            checked = e.value == "checked"
            if role == "check box" and DECLARE.search(name):
                # "I declare / I agree …" is a question of its own, whatever heading sits above it.
                fields.append(Field(e.id, name, "declare", required=True, value="checked" if checked else ""))
                texts, group_open, group_name = [], False, ""
                continue
            kind = "radio" if role == "radio button" else "check"
            if group_open and fields and fields[-1].kind == kind:
                fields[-1].options.append(Option(e.id, name, checked))
                continue
            question, help_text = _question(texts, group_name)
            fields.append(Field(e.id, question or name, kind, required="*" in question,
                                help=help_text, options=[Option(e.id, name, checked)]))
            texts, group_open, group_name = [], True, ""
            continue
        own = name if norm(name) not in GENERIC else ""
        question, help_text = _question(texts, own)
        title = question or own
        if not title:
            continue
        kind = "select" if role == "combo box" else ("long" if e.bbox[3] - e.bbox[1] > 60 or "long" in norm(name) else "text")
        fields.append(Field(e.id, title.replace(" *", "").strip(), kind,
                            required="*" in (question or "") or "*" in name or "required" in norm(help_text),
                            help=help_text, value="" if e.is_password else (e.value or ""),
                            sensitive=e.is_password or bool(SENSITIVE.search(title))))
        texts, group_open, group_name = [], False, ""
    for f in fields:
        f.question = f.question.replace(" *", "").strip()
        if f.kind in {"radio", "check"}:
            f.value = ", ".join(o.label for o in f.options if o.checked)
    # Hands act on the latest reading: form element ids become clickable and typeable.
    for e in doc:
        e.hwnd = w["hwnd"]
    h.last = Snapshot(w["hwnd"], w["title"], w["process"], doc, True, ("uia",), time.monotonic())
    return FormPage(w["hwnd"], w["title"], url, fields, nav, page, errors, closed, done)


def _question(texts: list[str], label: str = "") -> tuple[str, str]:
    """The question for the next input, and its help text.

    The page's own label for the input (aria-label / aria-labelledby) wins. Otherwise the question is the last
    title-like text before the input (a required star, or a short line not ending in a full stop); texts after
    it are help. Earlier texts (the form's title, a previous section) are ignored.
    """
    useful = [t for t in texts if norm(t) not in GENERIC and len(t) < 600]
    if label and norm(label) not in GENERIC:
        idx = next((i for i, t in enumerate(useful) if norm(t).rstrip(" *") == norm(label).rstrip(" *")), None)
        star = "*" in label or (idx is not None and "*" in useful[idx])
        question = label.rstrip(" *") + (" *" if star else "")
        return question, " ".join(useful[idx + 1:] if idx is not None else [])[:400]
    if not useful:
        return "", ""
    starred = [i for i, t in enumerate(useful) if t.rstrip().endswith("*")]
    if starred:
        i = starred[-1]
    else:
        titles = [i for i, t in enumerate(useful) if len(t) < 150 and not t.rstrip().endswith(".")]
        i = titles[-1] if titles else len(useful) - 1
    return useful[i], " ".join(useful[i + 1:])[:400]
