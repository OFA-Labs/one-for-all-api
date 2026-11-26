"""Shared helpers for the History test files (imported as ``history_support``)."""
from __future__ import annotations

import copy

from fastapi.testclient import TestClient

from history.store import HistoryStore
from history.seed import seed_user
from oneforall.api import create_app

TOKEN_A, TOKEN_B, TOKEN_SVC = "tok-a", "tok-b", "tok-svc"
TOKENS = {
    TOKEN_A: {"user": "user-a", "role": "member"},
    TOKEN_B: {"user": "user-b", "role": "member"},
    TOKEN_SVC: {"user": None, "role": "service"},
}
SECRET = b"test-cursor-secret-0123456789abcdef"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def history_config(tmp_path, **extra) -> dict:
    return {"data_dir": str(tmp_path / "history"), "tokens": TOKENS, "cursor_secret": SECRET,
            **extra}


def make_app(tmp_path, **history_extra):
    return create_app({"data_dir": str(tmp_path / "ebrain"), "tokens": {}},
                      history_config(tmp_path, **history_extra))


def make_client(tmp_path, **history_extra) -> TestClient:
    return TestClient(make_app(tmp_path, **history_extra))


def open_store(tmp_path, user: str) -> HistoryStore:
    return HistoryStore(str(tmp_path / "history"), {"cursor_secret": SECRET}, user)


def seed(tmp_path, user: str) -> dict:
    store = open_store(tmp_path, user)
    try:
        return seed_user(store, user, reset=False, now=1_700_000_000_000)
    finally:
        store.close()


def snapshot(user: str = "user-a", task_id: str = "task-1", **overrides) -> dict:
    """A minimal valid, terminal 'declined' snapshot; override any field."""
    base = {
        "task_id": task_id, "user_id": user, "goal": "A goal", "title": "A title",
        "state": "declined", "occurred_at": 1_763_278_440_000, "created_at": 1_763_278_200_000,
        "ended_at": 1_763_278_440_000,
        "events": [{"seq": 1, "at": 1_763_278_200_000, "type": "task.declined",
                    "message": "Declined."}],
    }
    return {**copy.deepcopy(base), **overrides}
