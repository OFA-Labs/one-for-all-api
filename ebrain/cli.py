"""HTTP-only agent bridges; the SQLite store remains the reference implementation."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from datetime import datetime
from typing import Any, Iterator

import httpx

from .models import KINDS
from .store import CODE_RE, SECRET_RE

DEFAULT_URL = "http://127.0.0.1:8765"
DEFAULT_PROJECT = "one-for-all"
SESSION_QUERY = "one-for-all project decisions architecture constraints"
REQUEST_TIMEOUT = 2.0  # LIMIT: per HTTP request, not a measured latency promise.
MARKER_RE = re.compile(r"(?:Decision:|Remember:)\s*(\S.*)")
ENTRY_RE = re.compile(r"^\s*(?:#{1,6}\s+|[-+*]\s+|\d+[.)]\s+)(\S.*)$")


class BridgeError(Exception):
    """An input or service failure suitable for a sanitized CLI diagnostic."""


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _versioned(text: str, identity: str) -> str:
    """EXPERIMENTAL: make ordinary durable notes usable by the reference retriever."""
    # UNTESTED: real-note slot quality and value-code collisions are unmeasured
    # | settle: T-083 real-note corpus; docs/ebrain/LIVE_VALIDATION.md LV-03.
    text = " ".join(text.splitlines()).strip()
    if not text:
        raise BridgeError("text must not be empty")
    if CODE_RE.search(text):
        return text
    digest = hashlib.sha256(f"{identity}|{text}".encode("utf-8")).digest()
    code = base64.b32encode(digest)
    return f"{text} (VC-{code.decode('ascii')[:6]})."


def _safe_text(text: str, token: str) -> str:
    redacted = SECRET_RE.sub("[REDACTED]", text)
    return redacted.replace(token, "[REDACTED]") if token else redacted


def _source(path: str, suffixes: tuple[str, ...]) -> Path:
    source = Path(path).expanduser().resolve()
    if (
        source.name.lower().startswith(".env")
        or source.suffix.lower() not in suffixes
    ):
        raise BridgeError(
            "unsupported input file; environment and key files are excluded"
        )
    if not source.is_file():
        raise BridgeError("input file does not exist")
    return source


def _hook_input() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError) as exc:
        raise BridgeError("invalid hook JSON input") from exc
    if not isinstance(data, dict):
        raise BridgeError("hook input must be an object")
    return data


def _post(client: httpx.Client, route: str, body: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/v1/ebrain/" + route, json=body)
    if not response.is_success:
        raise BridgeError(f"E-Brain service returned HTTP {response.status_code}")
    try:
        result = response.json()
    except ValueError as exc:
        raise BridgeError("invalid E-Brain service response") from exc
    if not isinstance(result, dict):
        raise BridgeError("invalid E-Brain service response")
    return result


def _write_body(
    args: argparse.Namespace,
    text: str,
    timestamp: int,
    op_id: str,
    kind: str,
    path: str | None = None,
) -> dict[str, Any]:
    return {
        "op_id": op_id,
        "ts": timestamp,
        "project_id": args.project,
        "visibility": args.visibility,
        "kind": kind,
        "text": _versioned(text, op_id),
        "path": path,
        "supersedes": getattr(args, "supersedes", []),
    }


def _accepted(result: dict[str, Any]) -> bool:
    if result.get("accepted") is not True:
        raise BridgeError(str(result.get("reason", "write rejected")))
    return result.get("reason") != "duplicate"


def _markdown_entries(source: Path) -> Iterator[tuple[int, str]]:
    """EXPERIMENTAL: import explicit Markdown headings and durable bullets."""
    # UNTESTED: line relocation can create new chains; no automatic deletion or
    # merge is safe | settle: T-083; docs/ebrain/LIVE_VALIDATION.md LV-03.
    fence: str | None = None
    # LIMIT: stream the input; each entry still obeys the store's max_text_chars.
    with source.open(encoding="utf-8-sig") as handle:
        for number, line in enumerate(handle, 1):
            stripped = line.lstrip()
            if stripped.startswith(("```", "~~~")):
                marker = stripped[:3]
                if fence is None:
                    fence = marker
                elif marker == fence:
                    fence = None
                continue
            if fence is None and (match := ENTRY_RE.match(line)):
                yield number, match.group(1).strip()


def _message_text(record: dict[str, Any]) -> str:
    message = record.get("message", record)
    if (
        not isinstance(message, dict)
        or message.get("role", record.get("type")) != "assistant"
    ):
        return ""
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            part["text"] for part in content
            if isinstance(part, dict) and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )
    return ""


def _durable_text(text: str) -> str:
    return " ".join(
        match.group(0).strip() for line in text.splitlines()
        if (match := MARKER_RE.search(line))
    )


def _timestamp(value: Any, fallback: int) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
        except ValueError:
            pass
    return fallback


def _capture(
    args: argparse.Namespace, client: httpx.Client, event: dict[str, Any]
) -> int:
    """EXPERIMENTAL: capture marked assistant text from Claude JSONL and Stop input."""
    # UNTESTED: live Claude streaming layouts and fallback-vs-flushed duplication
    # need an audit | settle: T-080; docs/ebrain/LIVE_VALIDATION.md LV-01/LV-04.
    if event.get("stop_hook_active") is True:
        return 0
    transcript = args.transcript or event.get("transcript_path")
    if not isinstance(transcript, str) or not transcript:
        if not isinstance(event.get("last_assistant_message"), str):
            raise BridgeError("capture requires a transcript path")
        source = None
    else:
        source = _source(transcript, (".jsonl", ".json"))
    count, seen = 0, set()
    if source is not None:
        # Missing message timestamps use the source's stable creation time where
        # available; zero means an undated source, never an invented message time.
        fallback = int(getattr(source.stat(), "st_birthtime", 0))
        # LIMIT: read one JSONL record at a time; never load a whole transcript.
        with source.open(encoding="utf-8-sig") as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except ValueError as exc:
                    raise BridgeError("invalid transcript JSONL record") from exc
                if not isinstance(record, dict):
                    continue
                text = _durable_text(_message_text(record))
                if not text:
                    continue
                seen.add(text)
                timestamp = _timestamp(record.get("timestamp"), fallback)
                identity = record.get("uuid", index)
                op_id = "capture-" + _digest(
                    f"{args.project}|{args.visibility}|"
                    f"{source}|{identity}|{timestamp}|{text}"
                )
                body = _write_body(args, text, timestamp, op_id, "log")
                count += _accepted(_post(client, "write", body))
    latest = _durable_text(str(event.get("last_assistant_message", "")))
    if latest and latest not in seen:
        # Stop may arrive before the final transcript record is flushed. The
        # stable fallback id prevents repeated Stop callbacks from adding rows.
        op_id = "stop-" + _digest(
            f"{args.project}|{args.visibility}|"
            f"{event.get('session_id', '')}|{latest}"
        )
        result = _post(client, "write", _write_body(
            args, latest, int(time.time()), op_id, "log"
        ))
        if result.get("reason") != "op_id reused with different content":
            count += _accepted(result)
    return count


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m ebrain")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("pack", "remember", "capture", "maintain", "import"):
        command = commands.add_parser(name)
        command.add_argument("--agent-token", default=None)
        command.add_argument("--project", default=DEFAULT_PROJECT)
        command.add_argument(
            "--visibility", choices=("shared", "private"), default="shared"
        )
        if name == "pack":
            command.add_argument("--text")
            # LIMIT: the reference's default proxy-token budget; no polling.
            command.add_argument("--budget", type=int, default=1024)
            command.add_argument("--hook", action="store_true")
        elif name == "remember":
            command.add_argument("--kind", choices=KINDS, required=True)
            command.add_argument("--text", required=True)
            command.add_argument("--path")
            command.add_argument("--supersedes", nargs="+", default=[])
        elif name == "capture":
            command.add_argument("--transcript")
            command.add_argument("--hook", action="store_true")
        elif name == "import":
            command.add_argument("--file", action="append", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = args.agent_token or os.environ.get("EBRAIN_AGENT_TOKEN", "")
    is_pack = args.command == "pack"
    try:
        if is_pack and (not token):
            return 0
        if not token:
            raise BridgeError("EBRAIN_AGENT_TOKEN is not configured")
        event = _hook_input() if getattr(args, "hook", False) else {}
        with httpx.Client(
            base_url=os.environ.get("EBRAIN_URL", DEFAULT_URL).rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=REQUEST_TIMEOUT,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            if is_pack:
                # UNTESTED: the broad SessionStart query is not exhaustive
                # | settle: T-080; docs/ebrain/LIVE_VALIDATION.md LV-04.
                text = args.text or event.get("prompt") or SESSION_QUERY
                if args.budget <= 0:
                    raise BridgeError("budget must be positive")
                result = _post(client, "query", {
                    "ts": int(time.time()), "text": text,
                    "project_id": args.project, "token_budget": args.budget,
                })
                rendered = result.get("rendered", "")
                if not isinstance(rendered, str):
                    raise BridgeError("invalid rendered memory response")
                if rendered:
                    print(_safe_text(rendered, token))
            elif args.command == "remember":
                timestamp = int(time.time())
                op_id = "cli-" + _digest(args.text + str(timestamp))
                result = _post(client, "write", _write_body(
                    args, args.text, timestamp, op_id, args.kind, args.path
                ))
                print(_safe_text(json.dumps(result), token))
                return 0 if result.get("accepted") is True else 1
            elif args.command == "capture":
                print(_capture(args, client, event))
            elif args.command == "maintain":
                result = _post(client, "maintain", {"now": int(time.time())})
                print(_safe_text(json.dumps(result.get("actions", [])), token))
            elif args.command == "import":
                count = 0
                for filename in args.file:
                    source = _source(filename, (".md",))
                    timestamp = int(source.stat().st_mtime)
                    for line, text in _markdown_entries(source):
                        path = f"{source}#L{line}"
                        op_id = "import-" + _digest(
                            f"{args.project}|{args.visibility}|"
                            f"{path}|{timestamp}|{text}"
                        )
                        body = _write_body(
                            args, text, timestamp, op_id, "decision", path
                        )
                        count += _accepted(_post(client, "write", body))
                print(count)
        return 0
    except (BridgeError, httpx.HTTPError, httpx.InvalidURL, OSError, ValueError) as exc:
        if is_pack:
            return 0
        message = (
            str(exc) if isinstance(exc, BridgeError)
            else "E-Brain input or connection unavailable"
        )
        print(_safe_text(message, token), file=sys.stderr)
        return 1
