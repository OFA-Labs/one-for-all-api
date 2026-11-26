"""The one action shape every effect passes through. Digest binds approvals to exact content."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    verb: str
    target: str | None = None            # app, window, url, element ref, path
    payload: str | None = None           # text to type/send, command line
    destinations: list[str] = Field(default_factory=list)
    account: str | None = None
    files: list[str] = Field(default_factory=list)      # sha256 of each file involved
    file_names: list[str] = Field(default_factory=list)
    handle: str | None = None            # vault/pm/session handle (never a value)
    element_label: str | None = None
    element_role: str | None = None
    key: str | None = None
    context: str | None = None           # e.g. compose, terminal, form, settings
    exists: bool | None = None           # for file.write: target already exists
    authorized_by_turn: str | None = None
    tier_hint: int | None = None
    args: dict[str, Any] = Field(default_factory=dict)

    def digest(self) -> str:
        body = self.model_dump(exclude={"id", "authorized_by_turn", "tier_hint"})
        if body.get("payload") is not None:
            body["payload"] = hashlib.sha256(body["payload"].encode()).hexdigest()
        raw = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()
