"""Opaque handle grammar: vault:<D0-D3>/<service>/<label>#<version> | pm:<manager>/<item>/<field> | session:<service>."""
from __future__ import annotations

import re
from dataclasses import dataclass

_VAULT = re.compile(r"^vault:(D[0-3])/([a-z0-9][a-z0-9._-]{0,63})/([a-z0-9][a-z0-9._-]{0,63})#(\d{1,6})$")
_PM = re.compile(r"^pm:(bitwarden|1password)/([A-Za-z0-9._-]{1,128})/(username|password|totp|[a-z0-9_]{1,32})$")
_SESSION = re.compile(r"^session:([a-z0-9][a-z0-9._-]{0,63})$")


class HandleError(ValueError):
    pass


@dataclass(frozen=True)
class Handle:
    kind: str            # vault | pm | session
    data_class: str      # D0..D3 (pm → D3 unless username, session → D0)
    service: str
    label: str
    version: int = 1
    raw: str = ""

    @property
    def base(self) -> str:
        return f"vault:{self.data_class}/{self.service}/{self.label}"


def format_vault(data_class: str, service: str, label: str, version: int) -> str:
    raw = f"vault:{data_class}/{service.lower()}/{label.lower()}#{version}"
    parse_handle(raw)
    return raw


def parse_handle(raw: str) -> Handle:
    if m := _VAULT.match(raw or ""):
        return Handle("vault", m[1], m[2], m[3], int(m[4]), raw)
    if m := _PM.match(raw or ""):
        cls = "D1" if m[3] == "username" else "D3"
        return Handle("pm", cls, m[1], f"{m[2]}/{m[3]}", 1, raw)
    if m := _SESSION.match(raw or ""):
        return Handle("session", "D0", m[1], "session", 1, raw)
    raise HandleError("Not a valid OFA handle")
