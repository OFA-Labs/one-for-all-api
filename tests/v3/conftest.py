"""Path helpers and markers for the isolated V3 test suite."""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

EVAL_SRC = os.path.join(ROOT, "tools", "ebrain", "v3-eval")
FIXTURES = os.path.join(EVAL_SRC, "fixtures")
CONTRACTS = os.path.join(ROOT, "docs", "ebrain", "contracts", "v3")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "m04_100k: full 100k deterministic generator workload")
    config.addinivalue_line(
        "markers", "ev_oracle: independent oracle / miniature history")


@pytest.fixture(scope="session")
def repo_root() -> str:
    return ROOT


@pytest.fixture(scope="session")
def fixture_dir() -> str:
    return FIXTURES


@pytest.fixture(scope="session")
def contracts_dir() -> str:
    return CONTRACTS


@pytest.fixture(scope="session")
def miniature() -> dict:
    with open(os.path.join(FIXTURES, "miniature_history.json"), encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def reviewed_miniature() -> dict:
    with open(os.path.join(FIXTURES, "expected_miniature.json"), encoding="utf-8") as fh:
        return json.load(fh)
