"""Typed launch configuration; browser input selects IDs, never these raw fields."""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from .contracts import Contract


class App(Contract):
    name: str
    executable: str = ""
    launch_kind: Literal["exe", "aumid", "shortcut", "registered_uri", "interactive_command"] = "exe"
    launch_identity: str = ""
    aliases: list[str] = Field(default_factory=list)
    arguments: list[str] = Field(default_factory=list)
    window_title: str | None = None
    writable: bool = False
    capture: bool = False
    working_directory: str = ""
    console_host: str = ""

    @model_validator(mode="after")
    def target_required(self) -> App:
        if self.launch_kind == "exe":
            self.executable = self.executable or self.launch_identity
            self.launch_identity = self.executable
        if not self.launch_identity:
            raise ValueError("Select a discovered launch identity")
        return self
