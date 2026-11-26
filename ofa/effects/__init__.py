"""Effects: what an already-authorised Action does. Only ofa.executor may call run_effect."""
from __future__ import annotations

from ..harness.api import Harness, HarnessError
from ..memory import Memory
from ..policy import Action
from ..vault.broker import Broker
from . import credentials, desktop, files, shell

DESKTOP = {
    "open": desktop.open_target, "windows": desktop.list_windows, "screen": desktop.read_screen,
    "focus": desktop.focus_window, "click": desktop.click, "double_click": desktop.click,
    "right_click": desktop.click, "drag": desktop.drag, "key": desktop.press_key, "scroll_up": desktop.scroll,
    "scroll_down": desktop.scroll, "wait_for": desktop.wait_for,
    **{op: desktop.window_operation for op in ("close", "minimize", "maximize", "restore", "snap_left", "snap_right")},
}


def run_effect(h: Harness, memory: Memory, broker: Broker | None, a: Action) -> dict:
    op = a.args.get("op")
    if op in DESKTOP:
        return DESKTOP[op](h, a)
    if op in {"type", "replace", "dictate"}:
        return desktop.type_into(h, a, replace=op == "replace")
    if op == "fill_secret":
        return credentials.fill_secret(h, broker, a)
    if op == "files":
        return files.search_files(memory, a)
    if op == "read_file":
        return files.read_file(memory, a.target or "")
    if op == "write_file":
        return files.write_file(memory, a)
    if op == "run_command":
        return shell.run_command(a)
    raise HarnessError("UNKNOWN_OP", str(op))
