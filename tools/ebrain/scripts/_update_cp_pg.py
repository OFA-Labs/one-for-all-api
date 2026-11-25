"""One-off: record real-Postgres checkpoint results."""
from __future__ import annotations

import csv
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "docs/ebrain/implementation-plan"
EVIDENCE = "evidence/20261125T054620Z-pg-integration/manifest.json"

PASS = {
    "CP8.1", "CP8.2", "CP8.3", "CP8.4", "CP8.5", "CP8.6", "CP8.7", "CP7.6",
}
NOTES = {
    "CP8.1": "Migration up/reapply, 15 tables, 15 FORCE RLS policies, restricted roles verified",
    "CP8.2": "Transaction-local scoped context, RLS denial probe, two-tenant isolation passed",
    "CP8.4": "Atomic admission, idempotent replay and concurrent last-slot conflict passed under org row lock",
    "CP8.5": "Outbox same-transaction job, lease/fencing, dead-letter and watermark passed",
    "CP8.7": "Suppression/erasure seam and safety-override refusal passed",
    "CP7.6": "D01/D03 principles approved in owner handover; schema fixtures pass; remaining ADR text reconciliation recorded",
}
path = PLAN / "CHECKPOINTS.csv"
with path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    cp = row["checkpoint_id"]
    if cp in PASS:
        row["status"] = "PASS"
        row["evidence"] = EVIDENCE
        row["blocker"] = ""
        if cp in NOTES:
            row["resume"] = NOTES[cp]
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("updated", len(PASS), "checkpoints")
