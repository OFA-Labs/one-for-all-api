"""One-off: record individual-edition verified results in checkpoints."""
from __future__ import annotations

import csv
from pathlib import Path

PLAN = Path(__file__).resolve().parents[3] / "docs/ebrain/implementation-plan"
UPDATES = {
    "CP13.5": ("PASS", "evidence/backup-drill/20261125T055939Z-backup-drill/manifest.json",
               "", "Owner key custody and production DR still pending; synthetic in-process key only"),
    "CP14.6": ("IN_PROGRESS", "evidence/individual-pilot/pilot.json",
               "Independent evaluator isolation not established; labels are local",
               "Run isolated OpenCode evaluator with independently labelled pilot set"),
    "CP12.6": ("IN_PROGRESS", "evidence/individual-benchmark/benchmark.json",
               "Measured exact-only latency/accuracy; component ablations still NOT_RUN",
               "Ablate lexical/vector/graph/rerank one at a time when models are activated"),
    "CP13.3": ("PASS", "evidence/20261125T055229Z-pg-integration/manifest.json",
               "", "CLI/MCP/voice/web schema-3 adapters implemented; live agent sessions NOT_RUN"),
}
path = PLAN / "CHECKPOINTS.csv"
with path.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
for row in rows:
    if row["checkpoint_id"] in UPDATES:
        status, evidence, blocker, resume = UPDATES[row["checkpoint_id"]]
        row.update(status=status, evidence=evidence, blocker=blocker, resume=resume)
with path.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print("updated", len(UPDATES))
