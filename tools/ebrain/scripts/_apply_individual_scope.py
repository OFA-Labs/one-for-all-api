"""One-off: apply individual-edition scope classification to checkpoints."""
from __future__ import annotations

import csv
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "docs/ebrain/implementation-plan"
OUT = {
    "CP13.1": "OUT_OF_SCOPE_CURRENT_RELEASE: live OIDC/SCIM deferred (D10); local scoped principals retained",
    "CP13.2": "OUT_OF_SCOPE_CURRENT_RELEASE: organization promotion/admin removed; single-owner scope retained",
    "CP13.6": "OUT_OF_SCOPE_CURRENT_RELEASE: 200-session enterprise matrix replaced by 1/3/5 same-owner agent sessions",
    "CP14.7": "OUT_OF_SCOPE_CURRENT_RELEASE: production cutover/deployment not authorized",
}
LIMITED = {
    "CP14.1": "IN_SCOPE_LIMITED: usage/resource accounting retained; tiers and price NULL deferred",
    "CP13.7": "IN_SCOPE_LIMITED: local safety signals only; enterprise on-call/SLA excluded",
}
path = PLAN / "CHECKPOINTS.csv"
with path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    cp = row["checkpoint_id"]
    if cp in OUT:
        row["status"] = "NOT_RUN"
        row["blocker"] = OUT[cp]
        row["resume"] = "No action in current release; preserve disabled code for future scope"
    elif cp in LIMITED:
        row["blocker"] = LIMITED[cp]
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("classified", len(OUT) + len(LIMITED), "checkpoints")
