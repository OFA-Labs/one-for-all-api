"""The seven fictional demo records: content, idempotency, reset scoping and the CLI."""
import pytest

from history import seed as seed_module
from history.models import TaskIn
from history_support import open_store, seed, snapshot

EXPECTED = {
    "sample-pr": ("Verified", "A", "2026-11-16T04:54:00+00:00", 45),
    "sample-jobs": ("Needs review", "none", "2026-11-16T04:12:00+00:00", 70),
    "sample-research": ("Verified", "A", "2026-11-15T12:40:00+00:00", 45),
    "sample-social": ("Submitted", "B", "2026-11-15T10:06:00+00:00", 80),
    "sample-refusal": ("Declined", "none", "2026-11-15T08:50:00+00:00", 20),
    "sample-paused": ("Paused", "none", "2026-11-14T05:38:00+00:00", 70),
    "sample-unknown": ("Unknown", "unknown", "2026-11-14T04:47:00+00:00", 45),
}


def test_seed_records_are_valid_and_labelled_as_demo():
    records = seed_module.seed_records("demo")
    assert [r.task_id for r in records] == list(EXPECTED)
    assert all(isinstance(r, TaskIn) and r.is_sample and r.user_id == "demo" for r in records)


def test_seeded_data_matches_the_documented_table(tmp_path):
    from datetime import datetime, timezone
    assert seed(tmp_path, "demo") == {"removed": 0, "created": 7, "unchanged": 0, "conflicts": 0}
    store = open_store(tmp_path, "demo")
    try:
        from history.store import build_filters
        items = {i["task_id"]: i for i in store.list_tasks(build_filters(), limit=50)["items"]}
        assert set(items) == set(EXPECTED)
        for task_id, (status, tier, utc, minutes) in EXPECTED.items():
            item = items[task_id]
            when = datetime.fromtimestamp(item["occurred_at"] / 1000, timezone.utc).isoformat()
            assert (item["display_status"], item["tier"], when, item["duration_ms"]) == (
                status, tier, utc, minutes * 60_000), task_id
            assert item["is_sample"] is True
        assert store.get_task("sample-pr")["event_count"] == 7
        assert store.get_task("sample-refusal")["event_count"] == 1
        assert all(store.get_task(i)["event_count"] >= 3 for i in items if i != "sample-refusal")
    finally:
        store.close()


def test_seeding_twice_creates_no_duplicates(tmp_path):
    seed(tmp_path, "demo")
    again = seed(tmp_path, "demo")
    assert again == {"removed": 0, "created": 0, "unchanged": 7, "conflicts": 0}


def test_reset_removes_only_demo_rows_for_that_user(tmp_path):
    from history.store import build_filters
    seed(tmp_path, "demo")
    seed(tmp_path, "other")
    store = open_store(tmp_path, "demo")
    try:
        store.ingest(TaskIn.model_validate(snapshot(user="demo", task_id="real-1")), now=1)
        result = seed_module.seed_user(store, "demo", reset=True, now=2)
        assert result == {"removed": 7, "created": 7, "unchanged": 0, "conflicts": 0}
        ids = {i["task_id"] for i in store.list_tasks(build_filters(), limit=50)["items"]}
        assert "real-1" in ids and len(ids) == 8
    finally:
        store.close()
    other = open_store(tmp_path, "other")
    try:
        assert other.list_tasks(build_filters())["total"] == 7
    finally:
        other.close()


def test_honesty_records_have_the_right_evidence(tmp_path):
    seed(tmp_path, "demo")
    store = open_store(tmp_path, "demo")
    try:
        unknown = store.get_task("sample-unknown")
        assert unknown["ledger"][0]["state"] == "intent"
        assert unknown["approvals"][0]["decision"] == "expired"
        assert "offline" in unknown["task"]["summary"].lower()
        assert unknown["task"]["tier"] == "unknown" and unknown["evidence"]["status"] == "unknown"
        social = store.get_task("sample-social")
        assert social["evidence"]["tier"] == "B" and social["evidence"]["url"] is None
        assert store.get_task("sample-refusal")["plan"]["sites"] == []
    finally:
        store.close()


def test_cli_seeds_multiple_users_and_prints_counts_only(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HISTORY_DATA_DIR", str(tmp_path / "unused"))
    assert seed_module.main(["--user", "demo", "--user", "second", "--reset",
                             "--data-dir", str(tmp_path / "cli")]) == 0
    out = capsys.readouterr().out
    assert "user='demo'" in out and "user='second'" in out and "'created': 7" in out
    assert "sample-pr" not in out and "Verified" not in out
    assert not (tmp_path / "unused").exists()


def test_cli_requires_a_user():
    with pytest.raises(SystemExit):
        seed_module.main([])
