"""Shell effect. Output passes the egress guard before it can reach the engine."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..egress import EGRESS, LeakBlocked
from ..policy import Action


def run_command(a: Action) -> dict:
    cwd = a.target if a.target and os.path.isdir(a.target) else str(Path.home())
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", a.payload or ""],
                         capture_output=True, text=True, timeout=60, cwd=cwd, creationflags=0x08000000)
    text = (out.stdout + ("\n" + out.stderr if out.stderr else ""))[-4000:]
    try:
        EGRESS.guard(text, "tool_output")
    except LeakBlocked:
        text = "[output withheld: it contained a protected value]"
    return {"exit_code": out.returncode, "output": text, "verified": out.returncode == 0}
