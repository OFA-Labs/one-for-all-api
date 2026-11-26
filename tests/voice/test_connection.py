from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from voice.connection import ConnectionLifecycle, IdentityLease


def test_connection_reuse_stop_signout_and_account_isolation(tmp_path: Path) -> None:
    async def run() -> None:
        now = [1.0]
        stops: list[str] = []

        async def stop() -> None:
            stops.append("mic_closed")

        profile = tmp_path / "profile.json"
        lease = IdentityLease("dev-user", "session-a", "device-a", "grant-a", "v1", 60)
        first = ConnectionLifecycle(profile, stop, lambda: now[0])
        first.attach(lease, explicit_connect=True)
        await first.stop_voice()
        first.authorize()  # Stop voice retained the connection.
        restored = ConnectionLifecycle(profile, stop, lambda: now[0])
        with pytest.raises(PermissionError):
            restored.authorize()  # Disk metadata alone never restores authority.
        restored.attach(lease)  # Reload/restart reuses consent with a trusted lease.
        restored.authorize()
        now[0] = 7
        with pytest.raises(PermissionError):
            restored.authorize()
        restored.heartbeat(lease)  # Temporary drop did not require pairing again.
        restored.authorize()
        await restored.signed_out("session-a")
        with pytest.raises(PermissionError):
            restored.attach(lease)
        other = replace(lease, principal_id="other-user", auth_session_id="session-b")
        with pytest.raises(PermissionError):
            restored.attach(other)
        restored.attach(other, explicit_connect=True)
        await restored.signed_out("session-a")  # A late old event cannot revoke the new user.
        restored.authorize()
        assert len(stops) == 2
    asyncio.run(run())
