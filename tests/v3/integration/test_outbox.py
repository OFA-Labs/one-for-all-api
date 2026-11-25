"""M8 CP8.5: crash/retry preserves acknowledged work and fences."""
from __future__ import annotations

from ebrain.v3.config import V3Config
from ebrain.v3.workers.outbox import Outbox
from ebrain.v3.contracts import OutboxJob

from ..v3_helpers import ctx, key, write


def test_job_in_same_transaction_as_event(pg_ledger, pg_conn):
    c = ctx()
    receipt = pg_ledger.admit(c, write("o1", key(), "v"))
    with pg_conn.cursor() as cur:
        cur.execute("SELECT job_id, state, seq FROM v3_outbox WHERE seq=%s",
                    (receipt.knowledge_seq,))
        row = cur.fetchone()
    assert row is not None and row[1] == "pending"


def test_outbox_lease_fence_and_dead_letter():
    outbox = Outbox(V3Config(outbox_max_attempts=2, job_lease_ticks=2))
    job = OutboxJob(job_id="j1", job_type="projection", scope="scope",
                    payload_digest="digest", knowledge_seq=1)
    assert outbox.enqueue(job) is True
    assert outbox.enqueue(job) is False
    leased = outbox.lease("w1", 1)
    assert len(leased) == 1
    assert outbox.apply("j1", "w2") is False  # wrong owner cannot apply
    assert outbox.apply("j1", "w1", fail=True) is False
    leased = outbox.lease("w1", 4)
    assert len(leased) == 1
    outbox.mark_contiguous(1)
    assert outbox.apply("j1", "w1") is True
    assert outbox.apply("j1", "w1") is False
    assert outbox.watermark == 1
