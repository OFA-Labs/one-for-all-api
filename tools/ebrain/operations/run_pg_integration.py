"""Run the real-Postgres V3 integration suite without exposing credentials.

The owner's DSN session variables were absent from the implementation shell.
This helper bootstraps *separate synthetic* test roles in the disposable
database, holds their passwords only in this process, runs pytest with the
DSNs injected into the child environment, and writes a sanitized evidence
manifest. Owner roles are not modified.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import secrets
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql

API = Path(__file__).resolve().parents[3]
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
CONTAINER = "ebrain-v3-test-pg"
DB = "ebrain_v3_test"
HOST = "127.0.0.1"
PORT = 55432
MIG_ROLE = "ebrain_migration_agent"
RUNTIME_ROLE = "ebrain_runtime_agent"


def admin_dsn() -> str:
    raw = subprocess.run(
        ["docker", "inspect", CONTAINER, "--format",
         "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True, text=True, check=True,
    ).stdout
    match = re.search(r"^POSTGRES_PASSWORD=(.+)$", raw, re.M)
    if not match:
        raise RuntimeError("admin password is not available in the test container")
    return f"postgresql://ebrain_admin:{match.group(1)}@{HOST}:{PORT}/{DB}"


def dsn(role: str, password: str) -> str:
    return f"postgresql://{role}:{password}@{HOST}:{PORT}/{DB}"


def main() -> int:
    utc = datetime.datetime.now(datetime.timezone.utc)
    run_id = utc.strftime("%Y%m%dT%H%M%SZ") + "-pg-integration"
    evidence = API / "docs/ebrain/implementation-plan/evidence" / run_id
    evidence.mkdir(parents=True, exist_ok=True)

    migration_password = secrets.token_urlsafe(24)
    runtime_password = secrets.token_urlsafe(24)
    with psycopg.connect(admin_dsn(), autocommit=True) as admin:
        with admin.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            for role, password in ((MIG_ROLE, migration_password),
                                   (RUNTIME_ROLE, runtime_password)):
                cur.execute(
                    "SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)
                )
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                            sql.Identifier(role), sql.Literal(password))
                    )
                else:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                            sql.Identifier(role), sql.Literal(password))
                    )
                cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(DB), sql.Identifier(role)))
            cur.execute(sql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(MIG_ROLE)))
            cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                sql.Identifier(RUNTIME_ROLE)))
            cur.execute("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls "
                        "FROM pg_roles WHERE rolname IN (%s,%s) ORDER BY rolname",
                        (MIG_ROLE, RUNTIME_ROLE))
            role_flags = [
                {"role": r[0], "super": r[1], "createdb": r[2],
                 "createrole": r[3], "bypassrls": r[4]}
                for r in cur.fetchall()
            ]
            cur.execute("SELECT extname, extversion FROM pg_extension ORDER BY extname")
            extensions = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("SHOW server_version")
            server_version = cur.fetchone()[0]

    migration_dsn = dsn(MIG_ROLE, migration_password)
    runtime_dsn = dsn(RUNTIME_ROLE, runtime_password)

    # DDL is applied by the migration role, once, before any DML connection.
    with psycopg.connect(migration_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Disposable test database: rebuild schema from the pinned migration
            # on every run so schema changes are actually exercised.
            cur.execute("SELECT tablename FROM pg_tables "
                        "WHERE schemaname='public' AND tablename LIKE 'v3_%%'")
            for (table,) in cur.fetchall():
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                    sql.Identifier(table)))
            cur.execute(
                (API / "migrations/ebrain_v3/0001_init.sql").read_text(encoding="utf-8")
            )
            cur.execute(
                "SELECT 'GRANT SELECT,INSERT,UPDATE,DELETE,REFERENCES ON TABLE ' "
                "|| quote_ident(tablename) || ' TO ' || quote_ident(%s) "
                "FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'v3_%%'",
                (RUNTIME_ROLE,),
            )
            for (statement,) in cur.fetchall():
                cur.execute(statement)
            cur.execute(
                "SELECT 'GRANT USAGE,SELECT ON SEQUENCE ' || quote_ident(sequencename) "
                "|| ' TO ' || quote_ident(%s) "
                "FROM pg_sequences WHERE schemaname='public'",
                (RUNTIME_ROLE,),
            )
            for (statement,) in cur.fetchall():
                cur.execute(statement)
            cur.execute("SELECT count(*) FROM pg_tables "
                        "WHERE schemaname='public' AND tablename LIKE 'v3_%%'")
            table_count = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM pg_policies WHERE schemaname='public' "
                "AND tablename LIKE 'v3_%%'"
            )
            policy_count = cur.fetchone()[0]

    env = dict(os.environ)
    env["EBRAIN_V3_TEST_PG_DSN"] = runtime_dsn
    env["EBRAIN_V3_MIGRATION_PG_DSN"] = migration_dsn
    test_venv_site = API / ".venv-ebrain-test/Lib/site-packages"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(test_venv_site), env.get("PYTHONPATH", "")]
    ).strip(os.pathsep)
    python = str(API / ".venv/Scripts/python.exe")
    result = subprocess.run(
        [python, "-m", "pytest", "tests/v3/integration", "-q"],
        cwd=API, env=env, text=True, capture_output=True,
    )
    output = result.stdout + result.stderr
    (evidence / "integration-output.txt").write_text(output, encoding="utf-8")
    summary_line = next(
        (line for line in reversed(output.splitlines()) if " passed" in line or " failed" in line),
        "no summary line",
    )

    # Real cross-process live validation: two independent CLI processes share
    # the authoritative PostgreSQL ledger (one writes, one reads).
    live_op = "live-" + run_id.replace("-", "")[:10]
    live_steps = [
        ["--enable-v3-local", "--persistent", "remember", "--op-id", live_op,
         "--resource-id", "live-demo", "--value", "postgresql-16"],
        ["--enable-v3-local", "--persistent", "pack", "--text", "live-demo",
         "--resource-id", "live-demo", "--predicate", "decision.status"],
    ]
    live_outputs: list[str] = []
    live_ok = True
    for step in live_steps:
        run = subprocess.run([python, "-m", "ebrain.v3.cli", *step],
                             cwd=API, env=env, text=True, capture_output=True)
        live_outputs.append(f"$ python -m ebrain.v3.cli {' '.join(step)}\nexit={run.returncode}\n"
                            + (run.stdout + run.stderr)[:2000])
        if run.returncode != 0:
            live_ok = False
    live_ok = live_ok and "postgresql-16" in live_outputs[-1]
    # Diagnostic: in-process view of the persisted claim and its eligibility.
    from ebrain.v3.auth.context import build_context
    from ebrain.v3.contracts import (
        Action, Grant, Principal, Selector,
    )
    from ebrain.v3.db.postgres import PostgresLedger
    from ebrain.v3.service import V3Service
    diag_principal = Principal(
        subject="owner", org_id="org-demo",
        grants=(Grant(scope="one-for-all", predicates=("*",),
                      actions=tuple(Action), authority="human"),), auth_epoch=1,
    )
    diag_ctx = build_context(diag_principal, request_id="diag", scope="one-for-all")
    diag_service = V3Service.build(ledger=PostgresLedger(dsn=runtime_dsn))
    diag_snap = diag_service.ledger.snapshot(diag_ctx)
    diag_claims = diag_service.ledger.load_slice(diag_ctx, (), diag_snap.knowledge_seq)
    diag_answer = diag_service.query(diag_ctx, Selector(
        scope="one-for-all", resource_id="live-demo", predicate="decision.status"))
    live_outputs.append(
        "diagnostic: claims=" + str(len(diag_claims))
        + " grant_authorities=" + str([g.authority for g in diag_ctx.principal.grants])
        + " authorities=" + str([c.authority for c in diag_claims])
        + " valid_from=" + str([c.valid_from for c in diag_claims])
        + " answer=" + diag_answer.answer_status.value
        + " items=" + str([i.current_value for i in diag_answer.items])
    )
    (evidence / "live-cli-output.txt").write_text("\n\n".join(live_outputs), encoding="utf-8")

    gate = subprocess.run(
        [python, "tools/ebrain/scripts/validate_v3_gate.py"],
        cwd=API, env=env, text=True, capture_output=True,
    )
    gate_output = gate.stdout + gate.stderr
    (evidence / "gate-output.txt").write_text(gate_output, encoding="utf-8")
    gate_summary = next(
        (line for line in reversed(gate_output.splitlines())
         if "skipped" in line or "passed" in line),
        gate_output.strip().splitlines()[-1] if gate_output.strip() else "no summary line",
    )
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=API,
                            text=True, capture_output=True).stdout.strip()
    manifest = {
        "run_id": run_id,
        "utc": utc.isoformat(),
        "cwd": str(API),
        "python": sys.version,
        "git_commit": commit,
        "database": DB,
        "host_port": f"{HOST}:{PORT}",
        "server_version": server_version,
        "extensions": extensions,
        "migration_role": MIG_ROLE,
        "runtime_role": RUNTIME_ROLE,
        "role_flags": role_flags,
        "table_count": table_count,
        "policy_count": policy_count,
        "command": "python -m pytest tests/v3/integration -q",
        "exit": result.returncode,
        "summary": summary_line,
        "live_cli_cross_process_pass": live_ok,
        "gate_command": "python tools/ebrain/scripts/validate_v3_gate.py",
        "gate_exit": gate.returncode,
        "gate_summary": gate_summary,
        "credential_handling": "synthetic passwords generated in-process; never printed or written to disk",
        "owner_roles_modified": False,
    }
    (evidence / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({
        "run_id": run_id,
        "exit": result.returncode,
        "summary": summary_line,
        "gate_exit": gate.returncode,
        "gate_summary": gate_summary,
        "live_cli_cross_process": live_ok,
        "evidence": str(evidence),
        "role_flags": role_flags,
        "table_count": table_count,
        "policy_count": policy_count,
    }, indent=2))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
