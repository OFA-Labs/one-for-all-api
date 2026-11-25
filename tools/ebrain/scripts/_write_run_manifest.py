"""One-off evidence manifest writer for the integrated V3 run."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

RUN_ID = os.environ.get("EBRAIN_RUN_ID", "20261125T024900Z-v3integrated")
root = Path(__file__).resolve().parents[3]
status = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                        text=True, cwd=root).stdout.splitlines()
digest = hashlib.sha256()
for line in sorted(status):
    path_part = line[3:].strip().strip('"')
    digest.update(line.encode("utf-8"))
    target = root / path_part
    if target.is_file():
        digest.update(hashlib.sha256(target.read_bytes()).digest())
    elif target.is_dir():
        for item in sorted(target.rglob("*")):
            if item.is_file() and ".venv" not in item.parts:
                digest.update(str(item.relative_to(root)).encode("utf-8"))
                digest.update(hashlib.sha256(item.read_bytes()).digest())

manifest = {
    "run_id": RUN_ID,
    "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "cwd": str(root),
    "python": sys.version,
    "git_commit": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                 text=True, cwd=root).stdout.strip(),
    "dirty_source_digest": digest.hexdigest(),
    "commands": [
        {
            "command": "python -m pytest tests -q (EBRAIN_FACTS_SOURCES set to retained CSVs)",
            "cwd": str(root), "exit": 0,
            "result": "157 passed, 17 skipped, 1 warning",
        },
        {
            "command": "python -m pytest tests/v3 -q",
            "cwd": str(root), "exit": 0,
            "result": "85 passed, 17 skipped, 1 warning",
        },
        {
            "command": "python tools/ebrain/scripts/validate_v3_gate.py --discover-only",
            "cwd": str(root), "exit": 0,
            "result": "29 mandatory pytest IDs discovered; missing=[]; M07 Playwright alias passed",
        },
    ],
    "blocked_environment": {
        "reason": "EBRAIN_V3_TEST_PG_DSN unset; no running Postgres/Docker daemon; psycopg not installed",
        "skipped_integration_tests": 17,
        "classification": "NOT_RUN / BLOCKED_ENVIRONMENT, never PASS",
    },
    "evidence_files": ["backend-full.txt", "v3-suite.txt", "gate-discovery.json"],
    "limitations": [
        "No real Postgres/RLS/concurrency proof",
        "No live model/provider, sealed evaluator, pilot or production deployment",
        "Web evidence is in evidence/M14-web-v3/",
    ],
}
path = root / "docs/ebrain/implementation-plan/evidence" / RUN_ID / "manifest.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(path)
print(manifest["dirty_source_digest"])
