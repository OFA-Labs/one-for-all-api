"""Password-manager delegation via official CLIs (§8.3 option 2). The user unlocks the manager
with its own UI/CLI; OFA never stores the manager's session or master password."""
from __future__ import annotations

import json
import os
import shutil
import subprocess


class PmError(RuntimeError):
    pass


def _run(args: list[str], env: dict | None = None, timeout: float = 20) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=env,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PmError("PM_UNAVAILABLE") from exc
    if out.returncode != 0:
        raise PmError("PM_LOCKED_OR_MISSING")
    return out.stdout


class Bitwarden:
    """`bw` CLI. The user runs `bw unlock` and exports BW_SESSION in the shell that starts OFA."""

    def __init__(self, exe: str | None = None):
        self.exe = exe or shutil.which("bw")

    def available(self) -> bool:
        return bool(self.exe)

    def status(self) -> str:
        if not self.exe:
            return "missing"
        try:
            return json.loads(_run([self.exe, "status"], dict(os.environ))).get("status", "unknown")
        except Exception:
            return "unknown"

    def items(self) -> list[dict]:
        data = json.loads(_run([self.exe, "list", "items"], dict(os.environ)))
        return [{"id": i["id"], "name": i.get("name", ""),
                 "uris": [u.get("uri") for u in (i.get("login") or {}).get("uris") or [] if u.get("uri")]}
                for i in data if i.get("type") == 1]

    def targets(self, item: str) -> list[str]:
        from .broker import origin_of
        for i in self.items():
            if i["id"] == item:
                return [o for o in (origin_of(u) for u in i["uris"]) if o]
        return []

    def get(self, item: str, field: str) -> str:
        if field == "totp":
            return _run([self.exe, "get", "totp", item], dict(os.environ)).strip()
        return _run([self.exe, "get", field, item], dict(os.environ)).strip()


class OnePassword:
    """`op` CLI with desktop-app integration (unlock via the 1Password app / Windows Hello)."""

    def __init__(self, exe: str | None = None):
        self.exe = exe or shutil.which("op")

    def available(self) -> bool:
        return bool(self.exe)

    def status(self) -> str:
        if not self.exe:
            return "missing"
        try:
            _run([self.exe, "whoami"])
            return "unlocked"
        except PmError:
            return "locked"

    def items(self) -> list[dict]:
        data = json.loads(_run([self.exe, "item", "list", "--categories", "Login", "--format", "json"]))
        return [{"id": i["id"], "name": i.get("title", ""), "uris": [u.get("href") for u in i.get("urls", [])]}
                for i in data]

    def targets(self, item: str) -> list[str]:
        from .broker import origin_of
        for i in self.items():
            if i["id"] == item:
                return [o for o in (origin_of(u) for u in i["uris"]) if o]
        return []

    def get(self, item: str, field: str) -> str:
        if field == "totp":
            return _run([self.exe, "item", "get", item, "--otp"]).strip()
        return _run([self.exe, "item", "get", item, "--fields", f"label={field}", "--reveal"]).strip()


def detect() -> dict:
    return {name: cls() for name, cls in (("bitwarden", Bitwarden), ("1password", OnePassword)) if cls().available()}
