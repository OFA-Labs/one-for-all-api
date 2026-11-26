"""Pure-function checks for the CI Postgres preparation helper."""
import importlib.util
from pathlib import Path

import pytest

HELPER = (
    Path(__file__).resolve().parents[1]
    / "tools" / "ebrain" / "scripts" / "ci_prepare_pg.py"
)


@pytest.fixture(scope="module")
def helper():
    spec = importlib.util.spec_from_file_location("ci_prepare_pg", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_role_dsn_targets_the_same_disposable_database(helper) -> None:
    dsn = helper.role_dsn(
        "postgresql://postgres:synthetic-only@localhost:5432/ebrain_v3_test",
        "ebrain_runtime_agent",
        "p@ss/word",
    )
    assert dsn == (
        "postgresql://ebrain_runtime_agent:p%40ss%2Fword@localhost:5432/ebrain_v3_test"
    )


def test_export_env_writes_both_mandatory_dsn_names(helper, tmp_path: Path) -> None:
    target = tmp_path / "github_env"
    helper.export_env(
        {helper.DSN_ENV: "runtime-dsn", helper.MIGRATION_ENV: "migration-dsn"},
        target,
    )
    exported = target.read_text(encoding="utf-8")
    assert "EBRAIN_V3_TEST_PG_DSN=runtime-dsn\n" in exported
    assert "EBRAIN_V3_MIGRATION_PG_DSN=migration-dsn\n" in exported
