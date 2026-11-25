"""Traceability: M04. Manifest declares exact/semantic matrix; execution remains NOT_RUN."""
from __future__ import annotations

import json

from ebrain.v3.config import V3Config

MANIFEST = {
    "sessions": (1, 25, 100, 200),
    "sizes_events": (1000, 10000, 50000, 100000),
    "sizes_distinct_facts": (1000, 10000, 50000, 100000),
    "workloads": {"read_heavy": 0.9, "mixed": 0.7},
    "metrics": ("p50", "p95", "p99", "errors", "throughput", "filtered_recall"),
    "hardware": "NOT_RUN",
}


def test_M04_manifest_and_scale(pg_ledger):
    assert MANIFEST["sessions"][-1] == 200
    assert MANIFEST["sizes_distinct_facts"][-1] == 100000
    assert V3Config().retrieval_budget_ms == 200
    assert json.dumps(MANIFEST)
    # Declaring a matrix is not an executed load result.
    assert MANIFEST["hardware"] == "NOT_RUN"
