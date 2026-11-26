"""Prepare a disposable PostgreSQL service for E-Brain V3 CI jobs.

The CI service database is synthetic and short-lived. This helper creates
separate migration and runtime roles (both non-superuser, NOBYPASSRLS), applies
the pinned V3 migration with the migration role, grants the runtime role DML
only, and writes both DSNs to ``$GITHUB_ENV`` for later steps.

Passwords are generated in this process and are never printed or written to
logs. Refuses to run without an explicit admin DSN so it can never be pointed
at an application database by accident. No owner credential is involved.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import quote, urlsplit

API_ROOT = Path(__file__).resolve().parents[3]
MIGRATION = API_ROOT / "migrations/ebrain_v3/0001_init.sql"
ADMIN_ENV = "CI_PG_ADMIN_DSN"
DSN_ENV = "EBRAIN_V3_TEST_PG_DSN"
MIGRATION_ENV = "EBRAIN_V3_MIGRATION_PG_DSN"
MIGRATION_ROLE = "ebrain_migration_agent"
RUNTIME_ROLE = "ebrain_runtime_agent"


def role_dsn(admin_dsn: str, role: str, password: str) -> str:
    """Build a role DSN for the same disposable service host/database."""
    parts = urlsplit(admin_dsn)
    host = parts.hostname or "localhost"
    port = parts.port or 5432
    database = parts.path.lstrip("/") or "ebrain_v3_test"
    return (
        f"postgresql://{quote(role, safe='')}:{quote(password, safe='')}"
        f"@{host}:{port}/{database}"
    )


def export_env(values: dict[str, str], github_env: Path) -> None:
    """Append DSN exports without echoing their values."""
    with github_env.open("a", encoding="utf-8") as handle:
        for name, value in values.items():
            handle.write(f"{name}={value}\n")


def prepare(admin_dsn: str) -> tuple[dict[str, str], dict[str, object]]:
    """Bootstrap roles/schema; return DSNs and a sanitized, loggable summary."""
    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:  # pragma: no cover - CI installs the driver
        raise SystemExit("psycopg 3 is required to prepare the CI Postgres") from exc

    migration_password = secrets.token_urlsafe(24)
    runtime_password = secrets.token_urlsafe(24)
    migration_dsn = role_dsn(admin_dsn, MIGRATION_ROLE, migration_password)
    runtime_dsn = role_dsn(admin_dsn, RUNTIME_ROLE, runtime_password)

    with psycopg.connect(admin_dsn, autocommit=True) as admin:
        database = admin.info.dbname
        with admin.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
            for role, password in (
                (MIGRATION_ROLE, migration_password),
                (RUNTIME_ROLE, runtime_password),
            ):
                cur.execute(
                    sql.SQL("SELECT 1 FROM pg_roles WHERE rolname = {}").format(
                        sql.Literal(role)
                    )
                )
                attributes = (
                    "WITH LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS"
                )
                if cur.fetchone():
                    cur.execute(
                        sql.SQL("ALTER ROLE {} " + attributes).format(
                            sql.Identifier(role), sql.Literal(password)
                        )
                    )
                else:
                    cur.execute(
                        sql.SQL("CREATE ROLE {} " + attributes).format(
                            sql.Identifier(role), sql.Literal(password)
                        )
                    )
                cur.execute(
                    sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(database), sql.Identifier(role)
                    )
                )
            cur.execute(
                sql.SQL("GRANT CREATE, USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(MIGRATION_ROLE)
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                    sql.Identifier(RUNTIME_ROLE)
                )
            )

    with psycopg.connect(migration_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'v3_%'"
            )
            for (table,) in cur.fetchall():
                cur.execute(
                    sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(
                        sql.Identifier(table)
                    )
                )
            cur.execute(MIGRATION.read_text(encoding="utf-8"))
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
                "|| ' TO ' || quote_ident(%s) FROM pg_sequences WHERE schemaname='public'",
                (RUNTIME_ROLE,),
            )
            for (statement,) in cur.fetchall():
                cur.execute(statement)
            cur.execute(
                "SELECT count(*) FROM pg_tables "
                "WHERE schemaname='public' AND tablename LIKE 'v3_%'"
            )
            table_count = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM pg_policies "
                "WHERE schemaname='public' AND tablename LIKE 'v3_%'"
            )
            policy_count = cur.fetchone()[0]

    if not table_count or not policy_count:
        raise SystemExit(
            "Pinned V3 migration produced no tables/policies; refusing to run tests"
        )
    dsns = {DSN_ENV: runtime_dsn, MIGRATION_ENV: migration_dsn}
    summary: dict[str, object] = {
        "roles": [MIGRATION_ROLE, RUNTIME_ROLE],
        "tables": table_count,
        "policies": policy_count,
        "database": database,
    }
    return dsns, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ci-prepare-pg")
    parser.add_argument(
        "--admin-dsn",
        default=os.environ.get(ADMIN_ENV),
        help=f"Disposable DB admin DSN (default: ${ADMIN_ENV})",
    )
    parser.add_argument(
        "--github-env",
        type=Path,
        default=Path(os.environ["GITHUB_ENV"]) if "GITHUB_ENV" in os.environ else None,
        help="GITHUB_ENV file to append DSN exports to",
    )
    args = parser.parse_args(argv)
    if not args.admin_dsn:
        raise SystemExit(f"Missing {ADMIN_ENV}; refusing to guess a database")
    if args.github_env is None:
        raise SystemExit("Missing GITHUB_ENV; this helper is for CI jobs only")
    if not MIGRATION.is_file():
        raise SystemExit(f"Missing pinned migration: {MIGRATION}")
    dsns, summary = prepare(args.admin_dsn)
    export_env(dsns, args.github_env)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
