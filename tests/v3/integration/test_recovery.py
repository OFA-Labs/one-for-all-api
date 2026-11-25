"""Traceability: C10."""
from __future__ import annotations

from ebrain.v3.contracts import WriteRequest
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.service import V3Service
from ebrain.v3.config import V3Config

from ..v3_helpers import ctx, key, write


def test_C10_no_resurrection(pg_ledger, pg_conn):
    c = ctx()
    led = MemoryLedger()
    led.admit(c, write("o1", key(), "secret"))
    seq_before = led.seq
    led.suppress(c, key().key_id, "erasure")
    assert led.is_suppressed(key().key_id)
    assert led.load_slice(c, (key(),), led.seq) == ()
    assert led.event_at(seq_before + 1)["type"] == "suppression"
    # History is preserved: suppression never physically deletes the event.
    assert led.event_at(seq_before)["type"] == "admission"


def test_postgres_suppression_removes_current(pg_ledger):
    from ebrain.v3.identity.keys import canonical_key
    from ebrain.v3.contracts import Action, ClaimKind, Grant, Principal, Selector
    from ebrain.v3.auth.context import build_context

    principal = Principal(
        subject="owner", org_id="org-demo",
        grants=(Grant(scope="proj-a", predicates=("*",), actions=tuple(Action),
                      authority="human"),), auth_epoch=1,
    )
    ctx = build_context(principal, request_id="suppress", scope="proj-a")
    key = canonical_key(
        org_id="org-demo", scope="proj-a", resource_namespace="repo",
        resource_id="sup-pg", predicate="decision.status", kind=ClaimKind.ASSERTION,
        qualifiers={"repo": "acme/api", "environment": "prod"},
    )
    receipt = pg_ledger.admit(ctx, write("sup1", key, "secret"))
    pg_ledger.suppress(ctx, receipt.fact_id or "", "erasure")
    claims = pg_ledger.load_slice(ctx, (key,), pg_ledger.snapshot(ctx).knowledge_seq)
    assert claims == ()
    assert receipt.fact_id in pg_ledger.suppressed_ids("org-demo")
