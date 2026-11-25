"""Deliberately broken contender: true current PLUS one stale zombie.

Used by tests and the ``evaluate`` CLI to confirm that joint exact rejects a
correct answer carrying one superseded value as current. It has no access to
oracle labels and implements only public rules.
"""
from __future__ import annotations

from typing import Any


class Adapter:
    name = "negative-control-true-plus-zombie"

    def __init__(self, config: dict[str, Any] | None = None,
                 workdir: str | None = None) -> None:
        self.config = config or {}

    def write(self, event: dict[str, Any]) -> dict[str, Any]:
        return {"status": "applied", "op_id": event.get("op_id")}

    def query(self, case: dict[str, Any]) -> dict[str, Any]:
        events = sorted(case.get("events") or [], key=lambda e: e["seq"])
        scope = str(case.get("scope", "s1"))
        as_of = int(case.get("as_of", 0))
        by_key: dict[str, dict[str, Any]] = {}
        stale: dict[str, dict[str, Any]] = {}
        for e in events:
            if e["scope"] != scope or e["ts"] > as_of:
                continue
            key = e["key"]
            stale.setdefault(key, e)
            if e.get("value") is not None:
                by_key[key] = e
        current: dict[str, dict[str, Any]] = {}
        for key, e in by_key.items():
            current[key] = {
                "value": e["value"], "state": "current",
                "provenance": [e["op_id"]], "facets": dict(e["facets"]),
            }
        # The zombie: an older value of an already-current key, asserted current.
        zombie_key = next((k for k, e in stale.items()
                           if k in current and e["op_id"] !=
                           by_key[k]["op_id"]), None)
        if zombie_key is not None:
            old = stale[zombie_key]
            current[zombie_key] = {
                "value": old.get("value"), "state": "current",
                "provenance": [old["op_id"]], "facets": dict(old["facets"]),
            }
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
