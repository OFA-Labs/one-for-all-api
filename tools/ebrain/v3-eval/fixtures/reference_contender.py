"""Test-only contender implementing the public rules from public events only.

This is NOT product code and is not imported by ``ebrain/``. It is used to
exercise the runner / evaluate CLI paths with a synthetic deterministic
contender. It never sees oracle hidden labels.
"""
from __future__ import annotations

from typing import Any


def _resolve(events: list[dict[str, Any]], scope: str,
             as_of: int) -> dict[str, dict[str, Any]]:
    max_ts: dict[str, int] = {}
    admitted: list[dict[str, Any]] = []
    for e in sorted(events, key=lambda x: x["seq"]):
        key = e["key"]
        prior = max_ts.get(key)
        if prior is not None and e["ts"] < prior:
            continue
        if e["ts"] > as_of:
            continue
        admitted.append(e)
        max_ts[key] = e["ts"] if prior is None else max(prior, e["ts"])
    by_key: dict[str, list[dict[str, Any]]] = {}
    for e in admitted:
        by_key.setdefault(e["key"], []).append(e)
    current: dict[str, dict[str, Any]] = {}
    for key, evs in by_key.items():
        scoped = [e for e in evs if e["scope"] == scope]
        if not scoped:
            continue
        last_ts = max(e["ts"] for e in scoped)
        group = [e for e in scoped if e["ts"] == last_ts]
        if (len(group) > 1 and len({e["source"] for e in group}) > 1
                and len({e["authority"] for e in group}) == 1
                and len({tuple(e["supersedes"]) for e in group}) == 1):
            continue  # unresolved conflict: no scalar current
        winner = max(scoped, key=lambda e: (e["ts"], e["seq"]))
        if winner["action"] == "erase":
            continue
        current[key] = {
            "value": winner["value"],
            "state": "current",
            "provenance": [winner["op_id"]],
            "facets": dict(winner["facets"]),
        }
    return current


class Adapter:
    name = "reference-fixture"

    def __init__(self, config: dict[str, Any] | None = None,
                 workdir: str | None = None) -> None:
        self.config = config or {}

    def write(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"status": "applied", "op_id": event.get("op_id")}

    def query(self, case: dict[str, Any]) -> dict[str, Any]:
        current = _resolve(list(case.get("events") or []),
                           str(case.get("scope", "s1")),
                           int(case.get("as_of", 0)))
        rendered = " ".join(str(v["value"]) for v in current.values()
                            if v.get("value") is not None)
        return {
            "query_id": case.get("query_id", "q"),
            "scenario": "sequential",
            "current": current,
            "answer_status": "complete",
            "abstained": not current,
            "delivered_facets": list(case.get("facets") or []),
            "rendered": rendered,
        }

    def close(self) -> None:
        return None
