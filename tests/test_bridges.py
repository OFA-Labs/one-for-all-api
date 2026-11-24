"""M1 spec amendment and M2 CLI, bootstrap and agent-hook contracts."""
from pathlib import Path

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Iterator
from collections.abc import Awaitable, Callable

import httpx
import pytest
import uvicorn
from starlette.requests import Request
from starlette.responses import Response

from ebrain.api import create_app
from ebrain.models import count_tokens

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT.parent / "one-for-all-web"
TOKENS = {
    "bridge-claude": {"user": "u-bridge", "agent": "claude", "human": False},
    "bridge-codex": {"user": "u-bridge", "agent": "codex", "human": False},
    "bridge-other": {"user": "u-other", "agent": "codex", "human": False},
    "bridge-human": {"user": "u-bridge", "agent": "human", "human": True},
}


@dataclass
class BridgeService:
    url: str
    data_dir: Path
    client: httpx.Client
    requests: list[tuple[str, str]]


@pytest.fixture
def bridge_service(tmp_path: Path) -> Iterator[BridgeService]:
    """Run the real API on a reserved loopback socket and an isolated database."""
    data_dir = tmp_path / "brain"
    app = create_app({"data_dir": str(data_dir), "tokens": TOKENS})
    requests: list[tuple[str, str]] = []

    @app.middleware("http")
    async def record_request(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        requests.append((request.method, request.url.path))
        return await call_next(request)

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(
            app, host="127.0.0.1", port=port, log_level="error", lifespan="off"
        ))
        thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listener]}, daemon=True
        )
        thread.start()
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.01)
        try:
            assert server.started, "Temporary bridge API did not start"
            with httpx.Client(
                base_url=f"http://127.0.0.1:{port}",
                headers={"Authorization": "Bearer bridge-claude"},
                timeout=5,
                trust_env=False,
            ) as client:
                yield BridgeService(str(client.base_url), data_dir, client, requests)
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "Temporary bridge API did not stop"


def _environment(service: BridgeService, token: str | None) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("EBRAIN_")}
    env.update({
        "EBRAIN_URL": service.url,
        "EBRAIN_DATA_DIR": str(service.data_dir),
        "CLAUDE_PROJECT_DIR": str(WEB),
        "PYTHONIOENCODING": "utf-8",
    })
    if token is not None:
        env["EBRAIN_AGENT_TOKEN"] = token
    return env


def _cli(
    service: BridgeService,
    *args: str,
    token: str | None = "bridge-claude",
    url: str | None = None,
    payload: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    env = _environment(service, token)
    if url is not None:
        env["EBRAIN_URL"] = url
    return subprocess.run(
        [sys.executable, "-m", "ebrain", *args],
        cwd=ROOT,
        env=env,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def _hook(
    service: BridgeService, command: str, payload: dict
) -> subprocess.CompletedProcess[str]:
    powershell = shutil.which("pwsh") or shutil.which("powershell")
    assert powershell, "PowerShell is required to verify the configured Windows hooks"
    return subprocess.run(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command],
        cwd=WEB,
        env=_environment(service, "bridge-claude"),
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def _rows(service: BridgeService) -> list[dict]:
    database = service.data_dir / "ebrain.sqlite"
    if not database.is_file():
        return []
    with sqlite3.connect(database) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("SELECT * FROM ops ORDER BY seq")]


def _items(
    service: BridgeService, text: str, token: str = "bridge-claude"
) -> list[dict]:
    response = service.client.post(
        "/v1/ebrain/query",
        json={"ts": 2 ** 62, "text": text, "token_budget": 1024},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    return response.json()["items"]


def test_spec_amended() -> None:
    spec = (
        Path(__file__).resolve().parents[2]
        / "one-for-all-web"
        / "docs"
        / "SPEC_ITERATION_1.md"
    ).read_text(encoding="utf-8")
    assert "intentionally blank placeholder" not in spec
    assert "**e-brain** shows the shared project memory (EXPERIMENTAL)" in spec


def test_claude_hooks(bridge_service: BridgeService, tmp_path: Path) -> None:
    """T-080 executes the shipped hooks, including capture before maintenance."""
    service = bridge_service
    seeded = service.client.post("/v1/ebrain/write", json={
        "op_id": "architecture-seed",
        "ts": 1,
        "visibility": "shared",
        "kind": "decision",
        "text": "Architecture decision: the project uses SQLite (VC-ARCH01).",
    })
    assert seeded.json() == {"accepted": True, "reason": ""}
    settings = json.loads((WEB / ".claude" / "settings.json").read_text(encoding="utf-8"))
    assert settings["attribution"]["commit"].endswith(
        "Co-Authored-By: One For All <noreply@one-for-all.local>"
    )
    start = settings["hooks"]["SessionStart"][0]["hooks"][0]
    stop = settings["hooks"]["Stop"][0]["hooks"][0]
    assert start["type"] == stop["type"] == "command"
    assert start["shell"] == stop["shell"] == "powershell"
    assert stop["command"].index("capture") < stop["command"].index("maintain")

    transcript = tmp_path / "session transcript.jsonl"
    transcript.write_text(json.dumps({
        "type": "assistant",
        "uuid": "durable-hook-note",
        "timestamp": "2026-11-24T02:00:00Z",
        "message": {"role": "assistant", "content": [
            {"type": "text", "text": "Decision: The deploy region is eu-west-1."},
        ]},
    }) + "\n", encoding="utf-8")
    payload = {
        "session_id": "bridge-session",
        "cwd": str(WEB),
        "transcript_path": str(transcript),
        "hook_event_name": "SessionStart",
    }
    packed = _hook(service, start["command"], payload)
    assert packed.returncode == 0, packed.stderr
    assert packed.stdout.lstrip().startswith("[e-brain memory")
    assert "SQLite" in packed.stdout

    service.requests.clear()
    payload["hook_event_name"] = "Stop"
    payload["stop_hook_active"] = False
    captured = _hook(service, stop["command"], payload)
    assert captured.returncode == 0, captured.stderr
    assert any("deploy region" in row["text"] and row["kind"] == "log"
               for row in _rows(service))
    writes = [index for index, request in enumerate(service.requests)
              if request == ("POST", "/v1/ebrain/write")]
    maintains = [index for index, request in enumerate(service.requests)
                 if request == ("POST", "/v1/ebrain/maintain")]
    assert writes and maintains and max(writes) < min(maintains)


def test_codex_block() -> None:
    """T-081 preserves the generated Next.js rules and adds canonical commands."""
    agents = (WEB / "AGENTS.md").read_text(encoding="utf-8")
    assert agents.index("<!-- END:nextjs-agent-rules -->") < agents.index(
        "python -m ebrain pack"
    )
    assert "python -m ebrain remember" in agents
    assert "EBRAIN_AGENT_TOKEN" in agents
    assert "one-for-all-api" in agents


def test_bootstrap(bridge_service: BridgeService, tmp_path: Path) -> None:
    """T-083 imports three independent facts without collapsing their histories."""
    source = tmp_path / "memory source.md"
    source.write_text(
        "- The deployment region is eu-west-1.\n"
        "- The cache provider is Redis.\n"
        "- The Node runtime is 24.\n",
        encoding="utf-8",
    )
    imported = _cli(bridge_service, "import", "--file", str(source))
    assert imported.returncode == 0, imported.stderr
    assert int(imported.stdout.strip()) == 3
    rows = _rows(bridge_service)
    assert len(rows) == 3
    assert all(row["kind"] == "decision" and row["path"] for row in rows)
    for number, row in enumerate(rows, start=1):
        origin, marker, line = row["path"].rpartition("#L")
        assert marker and Path(origin) == source.resolve() and line == str(number)
    for query, expected in (
        ("deployment region", "eu-west-1"),
        ("cache provider", "Redis"),
        ("Node runtime", "24"),
    ):
        assert any(expected in item["text"] and item["status"] == "current"
                   for item in _items(bridge_service, query))
    repeated = _cli(bridge_service, "import", "--file", str(source))
    assert repeated.returncode == 0, repeated.stderr
    assert len(_rows(bridge_service)) == 3
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        "# Build rules\n\n- The browser checks use Playwright.\n\n"
        "```md\n# An example heading is not memory\n"
        "- An example bullet is not memory\n```\n",
        encoding="utf-8",
    )
    combined = _cli(bridge_service, "import", "--file", str(source),
                    "--file", str(agents))
    assert combined.returncode == 0, combined.stderr
    assert int(combined.stdout.strip()) == 2
    assert len(_rows(bridge_service)) == 5


def test_bridge_remember_plain_text_and_supersedes(bridge_service: BridgeService) -> None:
    first = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                 "The auth token TTL is 45 minutes.", "--path", "docs/auth.md")
    assert first.returncode == 0, first.stderr
    assert json.loads(first.stdout)["accepted"] is True
    original = _rows(bridge_service)[0]
    assert original["agent"] == "claude" and original["auth"] == 0
    second = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                  "The auth token TTL is 30 minutes.", "--path", "docs/auth.md",
                  "--supersedes", original["op_id"])
    assert second.returncode == 0, second.stderr
    assert json.loads(second.stdout)["accepted"] is True
    rows = _rows(bridge_service)
    assert len(rows) == 2 and json.loads(rows[1]["sup"]) == [original["op_id"]]
    items = _items(bridge_service, "auth token TTL", "bridge-codex")
    assert any("30 minutes" in item["text"] for item in items)
    assert not any("45 minutes" in item["text"] for item in items)
    packed = _cli(bridge_service, "pack", "--text", "auth token TTL",
                  "--budget", "16")
    assert packed.returncode == 0, packed.stderr
    assert count_tokens(packed.stdout) <= 16
    # A legitimate new version may return to an earlier value. Wait for a new
    # second because the spec derives remember's op_id from text + integer ts.
    while int(time.time()) <= original["ts"]:
        time.sleep(0.02)
    reverted = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                    "The auth token TTL is 45 minutes.", "--path", "docs/auth.md",
                    "--supersedes", rows[1]["op_id"])
    assert reverted.returncode == 0, reverted.stderr
    assert json.loads(reverted.stdout)["accepted"] is True
    reverted_items = _items(bridge_service, "auth token TTL", "bridge-codex")
    assert any("45 minutes" in item["text"] for item in reverted_items)
    assert not any("30 minutes" in item["text"] for item in reverted_items)


def test_bridge_pack_preserves_private_and_user_scope(bridge_service: BridgeService) -> None:
    remembered = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                      "The wake word is Jarvis.", "--visibility", "private")
    assert remembered.returncode == 0, remembered.stderr
    for token, visible in (("bridge-claude", True), ("bridge-codex", False),
                           ("bridge-other", False)):
        packed = _cli(bridge_service, "pack", "--text", "wake word", token=token)
        assert packed.returncode == 0, packed.stderr
        assert ("Jarvis" in packed.stdout) is visible
    private = _rows(bridge_service)[0]
    while int(time.time()) <= private["ts"]:
        time.sleep(0.02)
    shared = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                  "The wake word is Jarvis.", token="bridge-codex")
    assert shared.returncode == 0, shared.stderr
    assert any("Jarvis" in item["text"] for item in _items(
        bridge_service, "wake word", "bridge-codex"
    ))
    assert _items(bridge_service, "wake word", "bridge-other") == []


def test_bridge_capture_only_durable_assistant_text_and_repeat(
    bridge_service: BridgeService, tmp_path: Path
) -> None:
    transcript = tmp_path / "capture.jsonl"
    records = [
        {"type": "user", "message": {"role": "user", "content":
            "Remember: A user line is not assistant output."}},
        {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "name": "Bash", "input": {
                "command": "Decision: A tool input must not be captured."}},
        ]}},
        {"type": "assistant", "uuid": "capture-1", "timestamp": "2026-11-24T02:00:00Z",
         "message": {"role": "assistant", "content": [
             {"type": "text", "text": "Decision: The package manager is npm."},
             {"type": "tool_use", "name": "Read", "input": {"file_path": "ignored"}},
         ]}},
        {"type": "assistant", "uuid": "capture-2", "timestamp": "2026-11-24T02:00:01Z",
         "message": {"role": "assistant", "content":
             "Remember: The test runner is pytest."}},
        {"type": "assistant", "message": {"role": "assistant", "content":
            "This ordinary progress message is not a durable note."}},
    ]
    transcript.write_text("".join(json.dumps(record) + "\n" for record in records),
                          encoding="utf-8")
    captured = _cli(bridge_service, "capture", "--transcript", str(transcript))
    assert captured.returncode == 0, captured.stderr
    assert int(captured.stdout.strip()) == 2
    rows = _rows(bridge_service)
    assert len(rows) == 2 and all(row["kind"] == "log" for row in rows)
    assert all("user line" not in row["text"] and "tool input" not in row["text"]
               for row in rows)
    repeated = _cli(bridge_service, "capture", "--transcript", str(transcript))
    assert repeated.returncode == 0, repeated.stderr
    assert len(_rows(bridge_service)) == 2
    fallback = {
        "session_id": "unflushed-session",
        "last_assistant_message": "Remember: The fallback queue is durable.",
    }
    unflushed = _cli(bridge_service, "capture", "--hook", payload=fallback)
    assert unflushed.returncode == 0, unflushed.stderr
    assert int(unflushed.stdout.strip()) == 1
    fallback_row = _rows(bridge_service)[-1]
    while int(time.time()) <= fallback_row["ts"]:
        time.sleep(0.02)
    retried = _cli(bridge_service, "capture", "--hook", payload=fallback)
    assert retried.returncode == 0, retried.stderr
    assert int(retried.stdout.strip()) == 0
    assert len(_rows(bridge_service)) == 3
    rejected = _cli(bridge_service, "capture", "--hook", payload={
        "session_id": "oversized-session",
        "last_assistant_message": "Decision: " + "oversized input " * 2000,
    })
    assert rejected.returncode != 0
    assert "bad text" in rejected.stderr
    assert len(_rows(bridge_service)) == 3


def test_bridge_pack_quiet_when_unavailable_or_unconfigured(
    bridge_service: BridgeService,
) -> None:
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        unavailable_url = f"http://127.0.0.1:{reserved.getsockname()[1]}"
    unavailable = _cli(bridge_service, "pack", "--text", "auth TTL",
                       url=unavailable_url)
    assert unavailable.returncode == 0 and unavailable.stdout == ""
    unconfigured = _cli(bridge_service, "pack", "--text", "auth TTL", token=None)
    assert unconfigured.returncode == 0 and unconfigured.stdout == ""


def test_bridge_write_auth_failures_are_explicit_and_sanitized(
    bridge_service: BridgeService,
) -> None:
    unknown_token = "bridge-invalid-token-never-echo-this"
    rejected = _cli(bridge_service, "remember", "--kind", "decision", "--text",
                    "The auth token TTL is 30 minutes.", token=unknown_token)
    assert rejected.returncode != 0
    assert unknown_token not in rejected.stdout + rejected.stderr
    assert "Traceback" not in rejected.stderr
    assert _rows(bridge_service) == []


def test_bridge_agent_cannot_use_human_actions(bridge_service: BridgeService) -> None:
    for endpoint, body in (
        ("/v1/ebrain/rollback", {"to_ts": 0}),
        ("/v1/ebrain/pairs/confirm", {"a": "x", "b": "y", "ts": 1}),
        ("/v1/ebrain/pairs/split", {"a": "x", "b": "y", "ts": 1}),
        ("/v1/ebrain/heal/missing/approve", {"ts": 1}),
        ("/v1/ebrain/resolve", {"chain": "x", "pick_op_id": "y", "ts": 1}),
    ):
        response = bridge_service.client.post(endpoint, json=body)
        assert response.status_code == 403
        assert response.json() == {"detail": "human token required"}

def test_bridge_stop_fallback_is_scoped_to_project(
    bridge_service: BridgeService, tmp_path: Path
) -> None:
    transcript = tmp_path / "unflushed-scope.jsonl"
    transcript.write_text("", encoding="utf-8")
    event = {
        "session_id": "same-stop-session",
        "transcript_path": str(transcript),
        "last_assistant_message": "Remember: The approval timeout is 30 seconds.",
    }
    first = _cli(bridge_service, "capture", "--hook", payload=event)
    assert first.returncode == 0, first.stderr
    assert first.stdout.strip() == "1"
    second = _cli(
        bridge_service, "capture", "--hook", "--project", "another-project",
        payload=event,
    )
    assert second.returncode == 0, second.stderr
    assert second.stdout.strip() == "1"
    rows = _rows(bridge_service)
    assert {row["project"] for row in rows} == {"one-for-all", "another-project"}
    assert len(rows) == 2
