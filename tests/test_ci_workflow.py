"""Regression guards for the E-Brain CI workflow used by GitHub checks.

The API legacy suite reads pinned files from a sibling web checkout, and the
release gate must execute the Postgres cases rather than skip them. These
invariants are cheap to assert as text so no YAML dependency is required.
"""
from pathlib import Path

import pytest

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ebrain-checks.yml"
)


@pytest.fixture(scope="module")
def workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_legacy_job_checks_out_sibling_web_repo(workflow: str) -> None:
    assert "repository: OFA-Labs/one-for-all-web" in workflow
    assert "path: web-checkout" in workflow
    assert "ref: staging" in workflow
    assert '"$GITHUB_WORKSPACE/../one-for-all-web"' in workflow
    assert ".venv/Scripts/python.exe" in workflow


def test_web_v3_job_is_defined_but_paused(workflow: str) -> None:
    # E-Brain work is paused: the job stays in the workflow for later, but is
    # skipped unless the repo variable is set and is not a release prerequisite.
    assert "  web-v3:" in workflow
    assert "if: ${{ vars.ENABLE_WEB_V3_CHECKS == 'true' }}" in workflow
    assert "run: npm run verify" in workflow
    assert "PLAYWRIGHT_BROWSERS_PATH: ./.cache/ms-playwright" in workflow
    assert "needs: [pure-and-legacy, postgres-integration]" in workflow
    assert "needs.web-v3.result" not in workflow


def test_postgres_jobs_prepare_real_dsns(workflow: str) -> None:
    # One preparation in the integration job and one in the release gate.
    assert workflow.count("tools/ebrain/scripts/ci_prepare_pg.py") >= 2
    assert workflow.count("pip install \"psycopg[binary]==3.2.9\"") >= 2


def test_release_gate_runs_gate_with_ci_python(workflow: str) -> None:
    assert "validate_v3_gate.py --python python" in workflow
