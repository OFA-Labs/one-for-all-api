"""M8 CP8.1/8.4: migration, atomic admission, idempotency under real Postgres."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from ebrain.v3.errors import IdempotencyConflict

from ..v3_helpers import ctx, key, write


def test_migration_up_and_reapply(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute("SELECT column_name FROM information_schema.columns "
                    "WHERE table_name='v3_claim'")
        columns = {row[0] for row in cur.fetchall()}
    assert {"org_id", "claim_id", "seq", "fact_key", "authority"} <= columns


def test_atomic_admission_and_idempotency(pg_ledger):
    c = ctx()
    k = key()
    first = pg_ledger.admit(c, write("o1", k, "v1", idem="i1"))
    replay = pg_ledger.admit(c, write("o1", k, "v1", idem="i1"))
    assert replay == first
    with pytest.raises(IdempotencyConflict):
        pg_ledger.admit(c, write("o2", k, "v2", idem="i1"))


def test_concurrent_last_slot_idempotency(pg_ledger):
    c = ctx()
    k = key()
    results: list[str] = []

    def run(n: int) -> None:
        try:
            pg_ledger.admit(c, write(f"c{n}", k, f"v{n}", idem="shared"))
            results.append("ok")
        except IdempotencyConflict:
            results.append("conflict")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, (1, 2)))
    assert sorted(results) == ["conflict", "ok"]
