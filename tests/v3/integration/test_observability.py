"""Traceability: M02."""
from __future__ import annotations

import json

from ebrain.v3.contracts import digest_of


def safe_signal(kind: str, count: int) -> dict[str, object]:
    """Low-cardinality metadata only: no query text, payload, bearer or names."""
    return {"kind": kind, "bucket": count // 10, "digest": digest_of({"kind": kind})}


def test_M02_safe_operational_signals(pg_ledger):
    signal = safe_signal("queue_lag", 37)
    serialized = json.dumps(signal)
    for forbidden in ("alice", "secret", "Bearer", "SELECT", "https://"):
        assert forbidden not in serialized
    assert signal["bucket"] == 3
