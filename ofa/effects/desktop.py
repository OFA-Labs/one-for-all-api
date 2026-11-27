"""Desktop effects: opening things, window operations, pointer, keyboard and typing."""
from __future__ import annotations

import re

from ..harness.api import Harness
from ..policy import Action
from .scopes import SCOPES

WEB_ADDRESS = re.compile(r"^[\w.-]+\.(com|org|net|in|io|ai|dev|co|app|edu|gov)(/\S*)?$", re.I)


def open_target(h: Harness, a: Action) -> dict:
    """Route "open X" to a URL, a path, a named folder or an installed app."""
    t = (a.target or "").strip()
    if re.match(r"^https?://", t, re.I):
        return h.open_url(t)
    if WEB_ADDRESS.match(t):
        return h.open_url("https://" + t)
    if t.startswith("ms-settings:") or re.match(r"^[a-zA-Z]:[\\/]", t) or t.startswith("\\\\"):
        return h.open_path(t)
    if t.casefold() in SCOPES:
        return h.open_path(str(SCOPES[t.casefold()]))
    return h.open_app(t)


def list_windows(h: Harness, a: Action) -> dict:
    return {"windows": h.windows()}


def read_screen(h: Harness, a: Action) -> dict:
    return h.screen(a.target, ocr=a.args.get("ocr"))


def focus_window(h: Harness, a: Action) -> dict:
    return h.focus(a.args.get("window") or a.target)


def window_operation(h: Harness, a: Action) -> dict:
    return h.window_op(a.args.get("window") or a.target, a.args["op"].removeprefix("snap_"))


def click(h: Harness, a: Action) -> dict:
    op = a.args["op"]
    double, button = op == "double_click", "right" if op == "right_click" else "left"
    if a.args.get("x") is not None:
        return h.click_point(a.args["x"], a.args["y"], double=double, button=button)
    return h.click(a.args["element"], double=double, button=button)


def drag(h: Harness, a: Action) -> dict:
    return h.drag(a.args["element"], a.args.get("to_element"))


def press_key(h: Harness, a: Action) -> dict:
    return h.key(a.key or "")


def scroll(h: Harness, a: Action) -> dict:
    return h.scroll("up" if a.args["op"] == "scroll_up" else "down", ref=a.args.get("element"))


def wait_for(h: Harness, a: Action) -> dict:
    return h.wait_for_text(a.payload or "", a.args.get("window"))


def type_into(h: Harness, a: Action, replace: bool) -> dict:
    text = a.payload or ""
    if not text:
        return {"status": "error", "reason": "NOTHING_TO_TYPE"}
    r = h.type_text(text, a.args.get("element"), replace=replace)
    rb = r.get("readback")
    if rb is not None:
        r["verified"] = " ".join(text.split()) in " ".join(rb.split())
        if not r["verified"]:
            r["note"] = "the field does not show exactly what was intended"
        r.pop("readback", None)
    else:
        r["verified"] = False
        r["note"] = "this app does not expose the field's text, so the typing could not be read back"
    return r
