"""Mandatory V3 gate: discover and run every traceability-named test.

Exit codes: 0 = all mandatory cases passed and executed; 2 = missing/skipped
mandatory case; 3 = execution failure. BLOCKED_ENVIRONMENT cases are reported
as NOT_RUN and make the release gate fail; they are never counted as PASS.
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[3]
TRACEABILITY = API_ROOT / "docs/ebrain/implementation-plan/TRACEABILITY.csv"


def named_tests() -> list[tuple[str, str]]:
    with TRACEABILITY.open(newline="", encoding="utf-8") as handle:
        return [
            (row["finding_id"], row["planned_test"])
            for row in csv.DictReader(handle)
            if "::" in row["planned_test"]
            and row["planned_test"].split("::")[0].endswith(".py")
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="validate-v3-gate")
    parser.add_argument("--python", default=str(API_ROOT / ".venv/Scripts/python.exe"))
    parser.add_argument("--discover-only", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    tests = named_tests()
    node_ids = [test for _, test in tests]
    cmd = [args.python, "-m", "pytest", "--collect-only", "-q", "tests/v3"]
    collected = subprocess.run(cmd, cwd=API_ROOT, text=True, capture_output=True)
    output = collected.stdout + collected.stderr
    missing = [node for node in node_ids if node not in output]
    report = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "cwd": str(API_ROOT),
        "named_tests": len(tests),
        "discovered": len(node_ids) - len(missing),
        "missing": missing,
        "discover_exit": collected.returncode,
        "execution": "NOT_RUN" if args.discover_only else "NOT_RUN",
    }
    if args.discover_only:
        code = 0 if not missing and collected.returncode == 0 else 2
    else:
        run = subprocess.run([args.python, "-m", "pytest", "-q", "tests/v3"],
                             cwd=API_ROOT, text=True, capture_output=True)
        tail = (run.stdout + run.stderr)[-4000:]
        skipped = "skipped" in tail
        report.update({
            "execution_exit": run.returncode,
            "skipped_present": skipped,
            "execution": "PASS" if run.returncode == 0 and not skipped else "NOT_RUN",
            "execution_tail": tail,
        })
        code = 0 if run.returncode == 0 and not skipped else 2
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "execution_tail"}, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
