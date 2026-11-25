"""Traceability: H07."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from ebrain.v3.contracts import UsageReservation
from ebrain.v3.errors import QuotaExceeded
from ebrain.v3.quotas.plans import PlanPolicy


def test_H07_atomic_reservations(pg_ledger):
    plan = PlanPolicy("individual_free")
    usage = UsageReservation(scope="proj-a", facts=999, events=0, plan_revision=plan.revision)
    plan.check(usage, UsageReservation(scope="proj-a", facts=1))
    with pytest.raises(QuotaExceeded):
        plan.check(usage, UsageReservation(scope="proj-a", facts=2))


def test_reservation_race_in_memory():
    from ebrain.v3.db.memory import MemoryLedger
    from ebrain.v3.quotas.plans import PlanPolicy as P
    from ..v3_helpers import ctx, write, key
    led = MemoryLedger(plan=P("individual_free"))
    c = ctx()
    outcomes: list[str] = []

    def run(n: int) -> None:
        try:
            led.admit(c, write(f"o{n}", key(), "v", idem=f"i{n}"))
            outcomes.append("ok")
        except Exception:
            outcomes.append("bounded")

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, range(10)))
    assert len(outcomes) == 10
    assert led.limits(c).active_facts == 1
