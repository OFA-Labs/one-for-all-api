"""Policy inputs taken from OFA's own screen reading, never from the model's claims."""
from __future__ import annotations

import re

from .harness.api import MARK, Harness, HarnessError
from .policy import Action

TERMINALS = {"windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "wt.exe", "conhost.exe",
             "alacritty.exe", "wezterm-gui.exe", "mintty.exe"}


def point_label(h: Harness, x: int, y: int) -> str | None:
    """What OFA itself saw at a screen point: a mark containing it, or the point the eyes last chose."""
    for el in (h.last.elements if h.last else []):
        l, t, r, b = el.bbox
        if l <= x < r and t <= y < b and (el.text or el.value):
            return el.text or el.value
    sight = h.last_sight or {}
    if sight.get("point") and abs(sight["point"][0] - x) <= 30 and abs(sight["point"][1] - y) <= 30:
        return sight.get("label") or None
    return None


def describe(h: Harness, action: Action) -> Action:
    ref = action.args.get("element")
    snap = h.last
    label = role = None
    ctx = action.context
    if ref and snap:
        try:
            el = snap.by_id(ref) if MARK.match(ref) else None
            if el:
                label, role = el.text or el.value or "", el.role
        except HarnessError:
            pass
    if snap:
        proc = snap.process
        if proc in TERMINALS:
            ctx = "terminal"
        elif role in {"edit", "document", "combo box"}:
            ctx = "search" if re.search(r"search|find|address|url|filter|khoj", (label or ""), re.I) else "compose"
        elif ctx is None and action.args.get("op") == "key":
            focused = None
            try:
                focused = h.b.focused_element()
            except Exception:
                pass
            if focused is not None and focused.role in {"edit", "document"}:
                ctx = "search" if re.search(r"search|find|address", focused.text or "", re.I) else "compose"
    if not label and action.args.get("x") is not None:
        label = point_label(h, action.args["x"], action.args["y"])
    return action.model_copy(update={"element_label": label or action.element_label,
                                      "element_role": role or action.element_role, "context": ctx})
