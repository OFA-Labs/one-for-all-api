"""Config-driven plan budgets. Labels are not measured guarantees; price is unset.

Legacy free event-count behaviour stays in schema 1. V3 counts active canonical
facts and separately bounds events, bytes, jobs, pending impacts and rate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

from ..contracts import Limits, UsageReservation
from ..errors import QuotaExceeded

# Plan capacity labels are configuration, not capability evidence.
PLANS: Final[Mapping[str, dict[str, object]]] = {
    "individual_free": {
        "label": "Individual engineering (free)",
        "facts": 1000, "events": 1000, "bytes": 8_388_608,
        "jobs": 1000, "pending": 100, "rate_per_min": 120,
        "evidence_status": "unmeasured",
    },
    "individual_paid_10k": {
        "label": "Individual engineering (10k)",
        "facts": 10_000, "events": 100_000, "bytes": 83_886_080,
        "jobs": 10_000, "pending": 1000, "rate_per_min": 600,
        "evidence_status": "unmeasured",
    },
    "individual_paid_50k": {
        "label": "Individual engineering (50k)",
        "facts": 50_000, "events": 500_000, "bytes": 419_430_400,
        "jobs": 50_000, "pending": 5000, "rate_per_min": 1200,
        "evidence_status": "unmeasured",
    },
    "company_50k": {
        "label": "Company (50k)",
        "facts": 50_000, "events": 500_000, "bytes": 419_430_400,
        "jobs": 50_000, "pending": 5000, "rate_per_min": 1200,
        "evidence_status": "unmeasured",
    },
    "company_100k": {
        "label": "Company (100k+)",
        "facts": 100_000, "events": 1_000_000, "bytes": 838_860_800,
        "jobs": 100_000, "pending": 10_000, "rate_per_min": 2400,
        "evidence_status": "unmeasured",
    },
}


@dataclass(frozen=True)
class PlanPolicy:
    plan_id: str
    revision: str = "1"
    emergency_fact_allowance: int = 25
    emergency_event_allowance: int = 100

    def limits(self, usage: UsageReservation, *, emergency: bool = False) -> dict[str, int]:
        plan = PLANS[self.plan_id]
        out: dict[str, int] = {}
        for key, field in (
            ("facts", "facts"), ("events", "events"), ("bytes", "bytes_"),
            ("jobs", "jobs"), ("pending", "pending"),
        ):
            cap = int(plan[key])  # type: ignore[index]
            if emergency and field in ("facts", "events"):
                cap += self.emergency_fact_allowance if field == "facts" else self.emergency_event_allowance
            out[key] = cap
        return out

    def check(
        self,
        usage: UsageReservation,
        delta: UsageReservation,
        *,
        emergency: bool = False,
    ) -> None:
        """Pure reservation check; caller must apply it under the commit lock."""
        caps = self.limits(usage, emergency=emergency)
        for name, cap in caps.items():
            current = getattr(usage, {"bytes": "bytes_"}.get(name, name))
            added = getattr(delta, {"bytes": "bytes_"}.get(name, name))
            if current + added > cap:
                raise QuotaExceeded(f"{name} budget exceeded for plan {self.plan_id}")

    def to_limits(self, scope: str, usage: UsageReservation) -> Limits:
        caps = self.limits(usage)
        plan = PLANS[self.plan_id]
        return Limits(
            scope=scope,
            plan_revision=self.revision,
            plan_label=str(plan["label"]),
            active_facts=usage.facts,
            fact_capacity=caps["facts"],
            events=usage.events,
            event_capacity=caps["events"],
            pending=usage.pending,
            jobs=usage.jobs,
            bytes_=usage.bytes_,
            price=None,
            evidence_status=str(plan["evidence_status"]),  # type: ignore[arg-type]
        )


DEFAULT_PLAN: Final = PlanPolicy("individual_free")
