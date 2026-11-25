"""One-off: record real-Postgres evidence in plan status documents."""
from __future__ import annotations

import csv
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "docs/ebrain/implementation-plan"
EVIDENCE = "evidence/20261125T054620Z-pg-integration/manifest.json"

PASS_NOW = {
    "C03", "C04", "C06", "C08", "C09", "C10",
    "H06", "H07", "H10", "M02", "M03",
}
UPDATE_NOTE = {
    "C04": PASS_NOW and "Real restricted roles + RLS denial probes passed; broader ANN/cache/backup paths still require pilot",
    "M04": "Manifest declared; load/saturation execution still NOT_RUN",
}

path = PLAN / "TRACEABILITY.csv"
with path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    finding = row["finding_id"]
    if finding in PASS_NOW:
        row["status"] = "PASS"
        row["evidence"] = EVIDENCE
    elif finding == "M04":
        row["evidence"] = EVIDENCE + " (fixture only; measured load NOT_RUN)"
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("updated", len(PASS_NOW), "findings")
