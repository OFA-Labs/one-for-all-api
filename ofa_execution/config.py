"""Nonsecret, explicitly scoped local permissions; default has no app access."""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field

from .contracts import Contract
from .launch_config import App


class LocalConfig(Contract):
    apps: list[App] = Field(default_factory=list)
    read_roots: list[str] = Field(default_factory=list)
    write_roots: list[str] = Field(default_factory=list)
    browser_command: list[str] = Field(default_factory=list)
    browser_backend: str = "browse"
    allowed_origins: list[str] = Field(default_factory=list)
    # Explicit fixture-only exception; never automatically enable localhost browsing.
    fixture_origins: list[str] = Field(default_factory=list)
    approval_seconds: int = Field(default=60, ge=1, le=300)
    max_tasks: int = Field(default=40, ge=1, le=200)
    # Launchers fill this in; "off" disables it. None keeps state in memory only.
    ledger_dir: str | None = None
    unknown_block_hours: int = Field(default=24, ge=1, le=8760)

    @classmethod
    def load(cls, path: str | None):
        return cls.model_validate(json.loads(Path(path).read_text(encoding="utf-8"))) if path else cls()

    def app(self, alias: str) -> App:
        from .contracts import ExecutionError
        matches = [a for a in self.apps if alias.casefold() in
                   {a.name.casefold(), *(x.casefold() for x in a.aliases)}]
        if len(matches) != 1:
            raise ExecutionError("APP_AMBIGUOUS" if matches else "APP_NOT_ALLOWED",
                                 "Choose an explicitly allowed application.",
                                 [{"id": a.name, "label": a.name} for a in matches or self.apps])
        app = matches[0]
        from .app_policy import allowed
        if not allowed(app):
            raise ExecutionError("POLICY_DENIED", "Protected settings, password managers and shells are excluded.")
        if app.launch_kind == "aumid":
            import re
            if not re.fullmatch(r"[\w.-]+_[\w]+![\w.-]+", app.launch_identity):
                raise ExecutionError("APP_NOT_FOUND", "Invalid installed application identity.")
        elif app.launch_kind == "shortcut":
            if Path(app.launch_identity).suffix.lower() != ".lnk" or not Path(app.launch_identity).is_file():
                raise ExecutionError("APP_NOT_FOUND", "The configured shortcut is not installed.")
        elif app.launch_kind == "interactive_command":
            if not Path(app.executable).is_file() or Path(app.console_host).name.lower() != "wt.exe" or not Path(app.console_host).is_file():
                raise ExecutionError("APP_NOT_FOUND", "The native Code executable or console host is unavailable.")
        elif app.launch_kind != "exe":
            raise ExecutionError("APP_UNSUPPORTED", "This launch mechanism is not enabled.")
        elif not Path(app.executable).is_file():
            raise ExecutionError("APP_NOT_FOUND", "The configured executable is not installed.")
        return app

    def file(self, raw: str, write: bool = False) -> Path:
        from .contracts import ExecutionError
        path = Path(raw).expanduser().resolve()
        roots = self.write_roots if write else self.read_roots + self.write_roots
        if not any(path.is_relative_to(Path(r).expanduser().resolve()) and
                   path != Path(r).expanduser().resolve() for r in roots):
            raise ExecutionError("PATH_NOT_ALLOWED", "The file is outside the consented folder scope.")
        if path.suffix.lower() not in {".txt", ".md", ".csv", ".json"}:
            raise ExecutionError("UNSUPPORTED_FILE", "Local file support is limited to bounded UTF-8 text files.")
        if path.exists() and path.stat().st_size > 65536:
            raise ExecutionError("FILE_TOO_LARGE", "Text file exceeds 64 KiB.")
        return path
