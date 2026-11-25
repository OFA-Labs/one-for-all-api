"""Traceability: C03."""
from __future__ import annotations

from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.resolver.policy import DEFAULT_POLICY
from ebrain.v3.resolver.reducer import Resolver

from ..v3_helpers import ctx, key, write


def test_C03_committed_write_worker_crash(pg_ledger, pg_conn):
    """A committed event is visible without waiting for any projection worker."""
    c = ctx()
    k = key()
    receipt = pg_ledger.admit(c, write("o1", k, "committed"))
    with pg_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM v3_claim WHERE seq=%s AND suppressed=false",
                    (receipt.knowledge_seq,))
        assert cur.fetchone()[0] == 1
        # No outbox application is performed: worker crash is simulated by absence.
        cur.execute("SELECT count(*) FROM v3_outbox WHERE seq=%s AND state='applied'",
                    (receipt.knowledge_seq,))
        assert cur.fetchone()[0] == 0


def test_in_memory_read_after_write():
    led = MemoryLedger()
    c = ctx()
    k = key()
    led.admit(c, write("o1", k, "committed"))
    snap = led.snapshot(c)
    claims = led.load_slice(c, (k,), snap.knowledge_seq)
    assert Resolver(DEFAULT_POLICY).resolve(claims, (), (), (), snap)
