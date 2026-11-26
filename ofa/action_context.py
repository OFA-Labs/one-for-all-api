"""Policy inputs taken from OFA's own screen reading, never from the model's claims."""
from __future__ import annotations

import re

from .harness.api import Harness, HarnessError
from .policy import Action

TERMINALS = {"windowsterminal.exe", "powershell.exe", "pwsh.exe", "cmd.exe", "wt.exe", "conhost.exe",
             "alacritty.exe", "wezterm-gui.exe", "mintty.exe"}


def describe(h: Harness, action: Action) -> Action:
    ref = action.args.get("element")
    snap = h.last
    label = role = None
    ctx = action.context
    if ref and snap:
        try:
            el = snap.by_id(ref) if ref[:1] in "uo" and ref[1:].isdigit() else None
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
    return action.model_copy(update={"element_label": label or action.element_label,
                                      "element_role": role or action.element_role, "context": ctx})
