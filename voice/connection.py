"""Connection grant outlives recording; only a trusted identity adapter supplies leases."""
from __future__ import annotations

import json
import os
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class IdentityLease:
    principal_id: str
    auth_session_id: str
    device_id: str
    grant_id: str
    consent_version: str
    expires_at: float
    mode: str = "development"


class ConnectionLifecycle:
    def __init__(self, profile: Path, stop_voice: Callable[[], Awaitable[None]],
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.profile, self.stop_voice, self.clock = profile, stop_voice, clock
        self.record: dict[str, str] = json.loads(profile.read_text()) if profile.exists() else {}
        self.lease: IdentityLease | None = None
        self.last_heartbeat = 0.0

    def _save(self) -> None:
        self.profile.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.profile.with_suffix(".partial")
        temporary.write_text(json.dumps(self.record), encoding="utf-8")
        os.replace(temporary, self.profile)

    def attach(self, lease: IdentityLease, *, explicit_connect: bool = False) -> None:
        if lease.expires_at <= self.clock():
            raise PermissionError("Expired identity lease")
        binding = {key: str(getattr(lease, key)) for key in (
            "principal_id", "auth_session_id", "device_id", "grant_id", "consent_version"
        )}
        reusable = self.record.get("active") == "true" and all(
            self.record.get(key) == value for key, value in binding.items()
        )
        if not reusable and not explicit_connect:
            raise PermissionError("An explicit connection/consent is required")
        self.record = {**binding, "active": "true", "mode": lease.mode}
        self.lease, self.last_heartbeat = lease, self.clock()
        self._save()

    def authorize(self) -> None:
        if (self.lease is None or self.record.get("active") != "true" or
                self.clock() >= self.lease.expires_at or
                self.clock() - self.last_heartbeat >= 5):
            raise PermissionError("Connection suspended; revalidate the existing grant")

    def heartbeat(self, lease: IdentityLease) -> None:
        self.attach(lease)

    async def suspend(self) -> None:
        self.lease = None
        await self.stop_voice()

    async def signed_out(self, auth_session_id: str) -> None:
        if self.record.get("auth_session_id") != auth_session_id:
            return
        self.record["active"] = "false"
        self._save()
        await self.suspend()
