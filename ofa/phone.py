"""Optional phone surface (§10.2 Option 1, Android over adb only — the host is Windows, so iPhone Mirroring
is impossible). Reimplemented from the Phone Harness design idea; no third-party code copied, no cloud,
no telemetry, no stealth. Every call goes through the hands graph policy like desktop actions."""
from __future__ import annotations

import re
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass


class PhoneError(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


@dataclass
class PEl:
    id: str
    text: str
    role: str
    bbox: tuple[int, int, int, int]
    is_password: bool = False

    def center(self):
        return (self.bbox[0] + self.bbox[2]) // 2, (self.bbox[1] + self.bbox[3]) // 2

    def public(self) -> str:
        return f'{self.id} {self.role} "{self.text[:80]}"' + (" [password]" if self.is_password else "")


def adb_runner(args: list[str], timeout: float = 15) -> str:
    exe = shutil.which("adb")
    if not exe:
        raise PhoneError("ADB_MISSING", "Android platform-tools (adb) is not installed")
    out = subprocess.run([exe, *args], capture_output=True, text=True, timeout=timeout, creationflags=0x08000000)
    if out.returncode != 0:
        raise PhoneError("ADB_FAILED", out.stderr.strip()[:200])
    return out.stdout


class Phone:
    def __init__(self, run=adb_runner, serial: str | None = None):
        self.run, self.serial = run, serial
        self.last: list[PEl] = []

    def _a(self, *args) -> str:
        return self.run((["-s", self.serial] if self.serial else []) + list(args))

    def devices(self) -> list[str]:
        lines = self.run(["devices"]).splitlines()[1:]
        return [l.split()[0] for l in lines if l.strip().endswith("device")]

    def ensure(self) -> str:
        devs = self.devices()
        if not devs:
            raise PhoneError("NO_DEVICE", "Connect your Android phone with USB debugging allowed")
        if self.serial is None:
            if len(devs) > 1:
                raise PhoneError("AMBIGUOUS", "Several phones are connected")
            self.serial = devs[0]
        state = self._a("shell", "dumpsys", "window")
        if re.search(r"mDreamingLockscreen=true|isStatusBarKeyguard=true|mShowingLockscreen=true", state):
            raise PhoneError("LOCKED", "Unlock your phone — PIN/biometrics are yours to do")
        return self.serial

    def screen(self) -> dict:
        self.ensure()
        self._a("shell", "uiautomator", "dump", "/sdcard/ofa_ui.xml")
        xml = self._a("exec-out", "cat", "/sdcard/ofa_ui.xml")
        root = ET.fromstring(xml[xml.index("<"):])
        out = []
        for node in root.iter("node"):
            text = node.get("text") or node.get("content-desc") or ""
            m = re.findall(r"\d+", node.get("bounds", ""))
            if not text or len(m) != 4:
                continue
            role = node.get("class", "").rsplit(".", 1)[-1].lower()
            out.append(PEl(f"p{len(out)}", text, role, tuple(map(int, m)), node.get("password") == "true"))
        self.last = out
        return {"elements": [e.public() for e in out[:60]], "count": len(out)}

    def element(self, ref: str) -> PEl:
        for e in self.last:
            if e.id == ref or e.text.casefold() == ref.casefold():
                return e
        raise PhoneError("ELEMENT_NOT_FOUND", ref)

    def tap(self, ref: str) -> dict:
        x, y = self.element(ref).center()
        self._a("shell", "input", "tap", str(x), str(y))
        time.sleep(0.4)
        return {"tapped": ref}

    def type_text(self, text: str) -> dict:
        safe = text.replace(" ", "%s")
        if re.search(r"[^\x20-\x7e]", text):
            raise PhoneError("UNICODE_UNSUPPORTED", "adb input text cannot type non-ASCII; use the phone keyboard")
        self._a("shell", "input", "text", re.sub(r"([\\\"'`$&|;<>()])", r"\\\1", safe))
        return {"typed": len(text)}

    def key(self, name: str) -> dict:
        codes = {"back": 4, "home": 3, "enter": 66, "recent": 187}
        self._a("shell", "input", "keyevent", str(codes[name]))
        return {"pressed": name}

    def open_app(self, package: str) -> dict:
        self._a("shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")
        return {"opened": package}

    def latest_sms_code(self, sender_hint: str) -> str | None:
        """Per-instance permission is enforced by the caller (Tier 2). Returns a digit code or None."""
        rows = self._a("shell", "content", "query", "--uri", "content://sms/inbox", "--projection", "address,body",
                       "--sort", "date DESC")
        for line in rows.splitlines()[:10]:
            if sender_hint.casefold() in line.casefold():
                m = re.search(r"\b(\d{4,8})\b", line.split("body=", 1)[-1])
                if m:
                    return m.group(1)
        return None
