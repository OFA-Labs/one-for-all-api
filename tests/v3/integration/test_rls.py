"""M8 CP8.2/3: FORCE RLS and restricted runtime role."""
from __future__ import annotations

import pytest

from ..v3_helpers import ctx, key, write


def test_every_tenant_table_has_force_rls(pg_conn):
    with pg_conn.cursor() as cur:
        cur.execute(
            "SELECT relname, relforcerowsecurity FROM pg_class "
            "WHERE relname LIKE 'v3_%' AND relkind='r'"
        )
        rows = dict(cur.fetchall())
    tenant_tables = [n for n in rows if not n.endswith("_seq")]
    assert tenant_tables
    assert all(rows[name] for name in tenant_tables), rows


def test_foreign_org_cannot_read_rows(pg_ledger, pg_conn):
    c = ctx()
    pg_ledger.admit(c, write("o1", key(), "secret"))
    with pg_conn.cursor() as cur:
        cur.execute("SELECT set_config('v3.org_id', %s, true)", ("org-other",))
        cur.execute("SELECT count(*) FROM v3_claim")
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT set_config('v3.org_id', %s, true)", ("org-demo",))
        cur.execute("SELECT count(*) FROM v3_claim")
        assert cur.fetchone()[0] == 1
