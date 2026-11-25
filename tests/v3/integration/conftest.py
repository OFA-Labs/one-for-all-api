"""Isolated Postgres fixtures.

Set ``EBRAIN_V3_TEST_PG_DSN`` to a dedicated, disposable test database and install
psycopg 3 in the test environment. Missing DSN/driver => BLOCKED_ENVIRONMENT
(NOT_RUN), never a skipped-PASS. Never point these fixtures at application data.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from ebrain.v3.db.postgres import (
    DSN_ENV_VAR,
    MIGRATION_ENV_VAR,
    PostgresLedger,
    psycopg_available,
)

MIGRATION = (Path(__file__).resolve().parents[3] / "migrations" / "ebrain_v3" / "0001_init.sql")
TABLES = (
    "v3_audit", "v3_receipt", "v3_claim", "v3_identity_event", "v3_decision",
    "v3_vote", "v3_outbox", "v3_pending_impact", "v3_usage", "v3_suppression",
    "v3_event", "v3_grant", "v3_principal", "v3_source_revision", "v3_org_state",
)


@pytest.fixture(scope="session")
def pg_module():
    missing = [name for name in (DSN_ENV_VAR, MIGRATION_ENV_VAR) if not os.environ.get(name)]
    if missing:
        pytest.skip(
            "BLOCKED_ENVIRONMENT: missing " + ", ".join(missing)
            + "; real Postgres/RLS claims are NOT_RUN",
            allow_module_level=True,
        )
    if not psycopg_available():
        pytest.skip(
            "BLOCKED_ENVIRONMENT: psycopg 3 is not installed; real Postgres "
            "claims are NOT_RUN",
            allow_module_level=True,
        )
    import psycopg
    return psycopg


@pytest.fixture(scope="session")
def pg_migrated(pg_module):
    """Apply DDL once with the migration role; never with the runtime role."""
    with pg_module.connect(os.environ[MIGRATION_ENV_VAR]) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('v3_org_state')")
            if cur.fetchone()[0] is None:
                cur.execute(MIGRATION.read_text(encoding="utf-8"))
    return True


@pytest.fixture()
def pg_conn(pg_module, pg_migrated):
    # Migration role seeds/resets fixtures; runtime role is used by pg_ledger for DML.
    dsn = os.environ[MIGRATION_ENV_VAR]
    conn = pg_module.connect(dsn)
    conn.autocommit = False
    with conn.cursor() as cur:
        # Establish trusted session context before seeding tenant rows.
        cur.execute("SELECT set_config('v3.org_id', %s, false)", ("org-demo",))
        for table in TABLES:
            cur.execute(f"TRUNCATE {table} CASCADE")
        cur.execute(
            "INSERT INTO v3_org_state(org_id, auth_epoch) VALUES ('org-demo', 1) "
            "ON CONFLICT (org_id) DO NOTHING"
        )
        cur.execute(
            "INSERT INTO v3_principal(org_id, subject, auth_epoch) VALUES ('org-demo','alice',1) "
            "ON CONFLICT DO NOTHING"
        )
    conn.commit()
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture()
def pg_ledger(pg_conn):
    return PostgresLedger(dsn=os.environ[DSN_ENV_VAR])
