"""Real-Postgres scale check through the product ledger (not an in-memory store).

Runs N atomic admissions and exact queries against the disposable database using
restricted runtime role. Reports distinct facts, joint exact and latency.
"""
from __future__ import annotations

import argparse
import datetime
import json
import secrets
import statistics
import sys
import time
from pathlib import Path

import psycopg
from psycopg import sql

API = Path(__file__).resolve().parents[3]
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
from tools.ebrain.operations.run_pg_integration import (  # noqa: E402
    DB, HOST, MIG_ROLE, PORT, RUNTIME_ROLE, admin_dsn, dsn,
)

OUT = API / "docs/ebrain/implementation-plan/evidence/pg-scale"


def setup() -> str:
    migration_password = secrets.token_urlsafe(24)
    runtime_password = secrets.token_urlsafe(24)
    with psycopg.connect(admin_dsn(), autocommit=True) as admin:
        with admin.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            for role, pw in ((MIG_ROLE, migration_password), (RUNTIME_ROLE, runtime_password)):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if cur.fetchone():
                    cur.execute(sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(pw)))
                else:
                    cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role), sql.Literal(pw)))
                cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(DB), sql.Identifier(role)))
            cur.execute(sql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(MIG_ROLE)))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(RUNTIME_ROLE)))
    mig_dsn = dsn(MIG_ROLE, migration_password)
    with psycopg.connect(mig_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'v3_%%'")
            for (table,) in cur.fetchall():
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(table)))
            cur.execute((API / "migrations/ebrain_v3/0001_init.sql").read_text(encoding="utf-8"))
            cur.execute("SELECT 'GRANT SELECT,INSERT,UPDATE,DELETE,REFERENCES ON TABLE '||quote_ident(tablename)||' TO '||quote_ident(%s) FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'v3_%%'", (RUNTIME_ROLE,))
            for (stmt,) in cur.fetchall():
                cur.execute(stmt)
            cur.execute("SELECT set_config('v3.org_id', %s, false)", ("org-demo",))
            cur.execute("INSERT INTO v3_org_state(org_id, auth_epoch) VALUES ('org-demo',1)")
            cur.execute("INSERT INTO v3_principal(org_id, subject, auth_epoch) VALUES ('org-demo','owner',1)")
    return dsn(RUNTIME_ROLE, runtime_password)


def main() -> int:
    parser = argparse.ArgumentParser(prog="pg-scale-check")
    parser.add_argument("--facts", type=int, default=10000)
    parser.add_argument("--queries", type=int, default=100)
    args = parser.parse_args()
    runtime_dsn = setup()

    from ebrain.v3.auth.context import build_context
    from ebrain.v3.config import V3Config
    from ebrain.v3.contracts import (
        Action, ClaimKind, Grant, Principal, Selector, WriteRequest,
    )
    from ebrain.v3.db.postgres import PostgresLedger
    from ebrain.v3.identity.keys import canonical_key
    from ebrain.v3.quotas.plans import PlanPolicy
    from ebrain.v3.service import V3Service

    principal = Principal(
        subject="owner", org_id="org-demo",
        grants=(Grant(scope="scale", predicates=("*",), actions=tuple(Action),
                      authority="human"),), auth_epoch=1,
    )
    ctx = build_context(principal, request_id="pg-scale", scope="scale")
    service = V3Service.build(cfg=V3Config(), plan=PlanPolicy("company_100k"),
                              ledger=PostgresLedger(
                                  dsn=runtime_dsn, plan=PlanPolicy("company_100k")))
    written = 0
    start = time.perf_counter()
    for n in range(args.facts):
        key = canonical_key(
            org_id="org-demo", scope="scale", resource_namespace="repo",
            resource_id=f"svc-{n}", predicate="decision.status",
            kind=ClaimKind.ASSERTION,
            qualifiers={"repo": "one-for-all-api", "environment": "dev"},
        )
        service.write(ctx, WriteRequest(
            op_id=f"scale-{n}", key=key, value=f"value-{n}", source_id="synthetic",
            source_revision="1", idempotency_key=f"scale-{n}",
            valid_from="2025-01-01T00:00:00+00:00",
        ))
        written += 1
    write_seconds = time.perf_counter() - start
    latencies: list[float] = []
    correct = 0
    for n in range(0, args.facts, max(1, args.facts // args.queries)):
        selector = Selector(
            scope="scale", predicate="decision.status", resource_id=f"svc-{n}",
            qualifiers=(("repo", "one-for-all-api"), ("environment", "dev")),
        )
        t0 = time.perf_counter()
        answer = service.query(ctx, selector)
        latencies.append((time.perf_counter() - t0) * 1000)
        if (answer.answer_status.value == "complete" and len(answer.items) == 1
                and answer.items[0].state.value == "current"
                and answer.items[0].current_value == f"value-{n}"):
            correct += 1
    report = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "database": f"postgresql://{HOST}:{PORT}/{DB} (restricted runtime role)",
        "facts_written": written,
        "queries": len(latencies),
        "joint_exact_correct": correct,
        "joint_exact": round(correct / len(latencies), 4) if latencies else 0,
        "write_seconds": round(write_seconds, 2),
        "latency_ms_p50": round(statistics.median(latencies), 3) if latencies else 0,
        "latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 3) if latencies else 0,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"pg-scale-{args.facts}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["joint_exact"] == 1.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
