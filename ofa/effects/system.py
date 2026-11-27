"""System controls: sound, media, brightness, lock, clipboard, screenshots, quick settings, processes.

Each control maps to a policy verb (ofa.policy.tiers): harmless controls are Tier 1, reading the clipboard
is Tier 2 unless the user said "clipboard", ending a process is always Tier 2. Settings → Hands can turn
system controls off.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
from pathlib import Path

from ..egress import EGRESS, LeakBlocked
from ..harness.api import Harness, HarnessError
from ..policy import Action

NO_WINDOW = 0x08000000
SETTINGS_PAGES = {"wifi": "ms-settings:network-wifi", "bluetooth": "ms-settings:bluetooth",
                  "airplane_mode": "ms-settings:network-airplanemode", "display": "ms-settings:display",
                  "sound": "ms-settings:sound", "battery": "ms-settings:batterysaver",
                  "notifications": "ms-settings:notifications", "night_light": "ms-settings:nightlight"}
KEYS = {"volume_up": "volume_up", "volume_down": "volume_down", "mute": "volume_mute",
        "play_pause": "media_play_pause", "next_track": "media_next", "previous_track": "media_prev"}

# control name -> policy verb
CONTROLS = {**{k: "system_control" for k in (*KEYS, "volume_set", "brightness_set", "lock", "clipboard_write",
                                              "screenshot_save", "settings_page")},
            "clipboard_read": "clipboard_read", "processes": "list_processes", "end_process": "end_process"}


def _powershell(script: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], input=stdin,
                          capture_output=True, text=True, timeout=20, creationflags=NO_WINDOW)


def _percent(value) -> int:
    try:
        n = int(float(str(value).rstrip("%")))
    except ValueError as exc:
        raise HarnessError("BAD_VALUE", "Give a number from 0 to 100") from exc
    return max(0, min(100, n))


def run_system(h: Harness, a: Action) -> dict:
    control, value = a.target or "", a.payload
    if control in KEYS:
        h.b.press(KEYS[control])
        return {"done": control, "verified": True}
    if control == "volume_set":
        level = _percent(value)
        for _ in range(50):                    # each key press moves the volume 2 %
            h.b.press("volume_down")
        for _ in range(level // 2):
            h.b.press("volume_up")
        return {"volume": level, "verified": True}
    if control == "brightness_set":
        level = _percent(value)
        out = _powershell("(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightnessMethods)"
                          f".WmiSetBrightness(1,{level})")
        if out.returncode != 0:
            return {"status": "error", "reason": "NO_BRIGHTNESS_CONTROL",
                    "detail": "This display does not let Windows change its brightness (external monitor?)"}
        return {"brightness": level, "verified": True}
    if control == "lock":
        ok = bool(ctypes.windll.user32.LockWorkStation()) if os.name == "nt" else False
        return {"locked": ok, "verified": ok}
    if control == "clipboard_write":
        out = _powershell("$input | Set-Clipboard", value or "")
        return {"copied": len(value or ""), "verified": out.returncode == 0}
    if control == "clipboard_read":
        text = _powershell("Get-Clipboard -Raw").stdout[:4000]
        try:
            EGRESS.guard(text, "tool_output")
        except LeakBlocked:
            text = "[withheld: the clipboard holds a protected value]"
        return {"clipboard": text, "verified": True}
    if control == "screenshot_save":
        path = Path(value or Path.home() / "Pictures" / "OFA screenshot.png")
        if path.suffix.lower() != ".png":
            path = path.with_suffix(".png")
        left, top, right, bottom = h.b.virtual_screen()
        bgra, width, height = h.b.capture((left, top, right, bottom))
        boxes = [e.bbox for e in (h.last.elements if h.last else []) if e.is_password]
        image = h.redact_capture(bgra, width, height, (left, top), boxes)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image.png)
        return {"saved": str(path), "verified": path.exists()}
    if control == "settings_page":
        page = SETTINGS_PAGES.get(str(value or "").casefold().replace(" ", "_").replace("-", "_"))
        if page is None:
            return {"status": "error", "reason": "UNKNOWN_PAGE", "options": sorted(SETTINGS_PAGES)}
        return h.open_path(page)
    if control == "processes":
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=20,
                             creationflags=NO_WINDOW)
        names = sorted({line.split('","')[0].strip('"') for line in out.stdout.splitlines() if line})
        return {"processes": names[:200], "verified": True}
    if control == "end_process":
        name = os.path.basename(str(value or ""))
        if not name or name.casefold() in {"explorer.exe", "winlogon.exe", "csrss.exe", "lsass.exe", "svchost.exe"}:
            return {"status": "refused", "reason": "PROTECTED_PROCESS"}
        out = subprocess.run(["taskkill", "/IM", name], capture_output=True, text=True, timeout=20,
                             creationflags=NO_WINDOW)
        return {"ended": name, "verified": out.returncode == 0, "detail": (out.stdout or out.stderr)[-200:]}
    raise HarnessError("UNKNOWN_CONTROL", control)
