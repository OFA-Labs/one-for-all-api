"""Traceability: C04 (in-memory paths; real RLS is a gated integration test)."""
from __future__ import annotations

import pytest

from ebrain.v3.clients.adapters import McpAdapter
from ebrain.v3.config import V3Config
from ebrain.v3.contracts import Selector
from ebrain.v3.errors import Forbidden, UnsupportedSchema

from ..test_pipeline_v3 import seeded_service
from ..v3_helpers import SCOPE, ctx, key, write


def test_C04_all_access_paths():
    svc = seeded_service()
    a = ctx(subject="alice", scope=SCOPE)
    b = ctx(subject="bob", scope="proj-b")
    secret_value = "scope-a-only"
    svc.write(a, write("s1", key(), secret_value))
    claims_b = svc.ledger.load_slice(b, (), svc.ledger.seq)
    assert all(c.key.scope != SCOPE for c in claims_b)
    assert all(secret_value not in str(c.value) for c in claims_b)
    answer_b = svc.query(b, Selector(scope="proj-b"))
    assert all(i.key.scope == "proj-b" for i in answer_b.items)
    with pytest.raises(Forbidden):
        svc.write(b, write("x", key(scope=SCOPE), "cross"))
    with pytest.raises(Forbidden):
        svc.ledger.admit(b, write("y", key(scope=SCOPE), "cross"))
    mcp = McpAdapter(svc, V3Config(mcp_enabled=True))
    assert mcp.tools()
    with pytest.raises(Exception):
        mcp.call_tool(b, "ebrain.write", {
            "op_id": "z", "key": key(scope=SCOPE).model_dump(mode="json"),
            "value": "cross", "source_id": "s", "source_revision": "1",
            "idempotency_key": "z",
        })
