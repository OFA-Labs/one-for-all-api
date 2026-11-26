"""HistoryStore: owner scoping, status mapping, search, cursors and pagination."""
import json
from pathlib import Path

import pytest

from history.errors import HistoryError
from history.models import TaskIn, display_status
from history.store import build_filters, decode_cursor, encode_cursor
from history_support import SECRET, open_store, seed, snapshot

FIXTURE = Path(__file__).parent / "fixtures" / "status_mapping.json"
ROWS = json.loads(FIXTURE.read_text(encoding="utf-8"))["rows"]
NOW = 1_700_000_000_000


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r['state']}-{r['tier']}-{r['evidence_status']}")
def test_status_mapping_fixture(row):
    assert display_status(row["state"], row["tier"], row["evidence_status"]) == row["display_status"]


def test_tier_d_is_never_verified():
    for evidence in ("verified", "submitted", "held", "unknown", "none"):
        assert display_status("completed", "D", evidence) != "Verified"


def ingest(store, **overrides):
    snap = TaskIn.model_validate(snapshot(user=store.u, **overrides))
    return store.ingest(snap, now=NOW)


def test_two_users_can_hold_the_same_task_ids(tmp_path):
    seed(tmp_path, "user-a")
    seed(tmp_path, "user-b")
    a, b = open_store(tmp_path, "user-a"), open_store(tmp_path, "user-b")
    try:
        assert a.list_tasks(build_filters())["total"] == 7
        assert b.list_tasks(build_filters())["total"] == 7
        assert a.get_task("sample-pr")["task"]["task_id"] == "sample-pr"
        assert open_store(tmp_path, "user-c").get_task("sample-pr") is None
    finally:
        a.close()
        b.close()


def test_other_users_ingest_never_conflicts_with_my_rows(tmp_path):
    a, b = open_store(tmp_path, "user-a"), open_store(tmp_path, "user-b")
    try:
        assert ingest(a, title="mine").status == 201
        assert ingest(b, title="theirs, same id, different content").status == 201
        assert a.get_task("task-1")["task"]["title"] == "mine"
    finally:
        a.close()
        b.close()


def test_search_is_case_insensitive_and_escapes_like_wildcards(tmp_path):
    store = open_store(tmp_path, "user-a")
    try:
        ingest(store, task_id="t1", title="100% done")
        ingest(store, task_id="t2", title="plain title")
        ingest(store, task_id="t3", title="under_score")
        ingest(store, task_id="t4", title="underXscore")
        ids = lambda q: {i["task_id"] for i in store.list_tasks(build_filters(q=q))["items"]}
        assert ids("100%") == {"t1"}
        assert ids("%") == {"t1"}
        assert ids("under_score") == {"t3"}
        assert ids("PLAIN") == {"t2"}
        assert ids("plain title") == {"t2"}
        assert ids("zzz") == set()
    finally:
        store.close()


def test_search_covers_title_subtitle_and_goal(tmp_path):
    store = open_store(tmp_path, "user-a")
    try:
        ingest(store, task_id="t1", title="x", subtitle="the subtitle word", goal="g")
        ingest(store, task_id="t2", title="y", goal="unique goal phrase")
        found = lambda q: {i["task_id"] for i in store.list_tasks(build_filters(q=q))["items"]}
        assert found("subtitle word") == {"t1"}
        assert found("goal phrase") == {"t2"}
    finally:
        store.close()


def test_pagination_covers_all_rows_once(tmp_path):
    seed(tmp_path, "user-a")
    store = open_store(tmp_path, "user-a")
    try:
        f = build_filters()
        seen, sizes, cursor = [], [], None
        while True:
            page = store.list_tasks(f, cursor=cursor, limit=3)
            sizes.append(len(page["items"]))
            seen += [i["task_id"] for i in page["items"]]
            assert page["total"] == 7
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert sizes == [3, 3, 1]
        assert len(seen) == len(set(seen)) == 7
        assert seen[0] == "sample-pr"  # newest first
        oldest = store.list_tasks(build_filters(sort="oldest"), limit=1)["items"][0]
        assert oldest["task_id"] == "sample-unknown"
    finally:
        store.close()


def test_cursor_is_stable_with_equal_timestamps(tmp_path):
    store = open_store(tmp_path, "user-a")
    try:
        for n in range(5):
            ingest(store, task_id=f"same-{n}")  # identical occurred_at
        f = build_filters()
        first = store.list_tasks(f, limit=2)
        second = store.list_tasks(f, cursor=first["next_cursor"], limit=2)
        third = store.list_tasks(f, cursor=second["next_cursor"], limit=2)
        ids = [i["task_id"] for p in (first, second, third) for i in p["items"]]
        assert ids == [f"same-{n}" for n in (4, 3, 2, 1, 0)]
        assert third["next_cursor"] is None
    finally:
        store.close()


def test_cursor_tampering_sort_and_filter_binding(tmp_path):
    seed(tmp_path, "user-a")
    store = open_store(tmp_path, "user-a")
    try:
        f = build_filters()
        cursor = store.list_tasks(f, limit=2)["next_cursor"]
        for bad in (cursor + "0", "x." + cursor.split(".")[1], "nonsense", cursor.split(".")[0],
                    cursor[:-3] + "AAA"):
            with pytest.raises(HistoryError) as err:
                store.list_tasks(f, cursor=bad, limit=2)
            assert (err.value.status, err.value.code) == (400, "invalid_cursor")
        # sort mismatch, and filter mismatch (q / status / tz), are all rejected
        for other in (build_filters(sort="oldest"), build_filters(q="pr"),
                      build_filters(status="Verified"), build_filters(tz="UTC")):
            with pytest.raises(HistoryError) as err:
                store.list_tasks(other, cursor=cursor, limit=2)
            assert err.value.code == "invalid_cursor"
    finally:
        store.close()


def test_cursor_signed_with_another_secret_is_rejected():
    f = build_filters()
    forged = encode_cursor(b"another-secret", 1, "x", "newest", f.fingerprint())
    with pytest.raises(HistoryError):
        decode_cursor(SECRET, forged, "newest", f.fingerprint())
    good = encode_cursor(SECRET, 5, "abc", "newest", f.fingerprint())
    assert decode_cursor(SECRET, good, "newest", f.fingerprint()) == (5, "abc")


def test_filters_validate_their_inputs():
    for kwargs in ({"status": "nope"}, {"state": "nope"}, {"tier": "Z"}, {"sort": "random"},
                   {"include_sample": "2"}, {"q": "x" * 201}):
        with pytest.raises(HistoryError) as err:
            build_filters(**kwargs)
        assert err.value.status == 400
    for kwargs in ({"tz": "Not/AZone"}, {"tz": "../etc/passwd"}, {"tz": "x" * 80}):
        with pytest.raises(HistoryError) as err:
            build_filters(**kwargs)
        assert err.value.code == "invalid_timezone"
    for kwargs in ({"from_": "2026-1-1"}, {"from_": "20261116"}, {"from_": "2026-02-30"},
                   {"from_": "2026-11-16", "to": "2026-11-16"},
                   {"from_": "2026-11-17", "to": "2026-11-16"}):
        with pytest.raises(HistoryError) as err:
            build_filters(**kwargs)
        assert err.value.code == "invalid_range"


def test_include_sample_filter_and_delete_samples_keep_real_rows(tmp_path):
    seed(tmp_path, "user-a")
    store = open_store(tmp_path, "user-a")
    try:
        ingest(store, task_id="real-1", is_sample=False)
        assert store.list_tasks(build_filters(include_sample="0"))["total"] == 1
        assert store.list_tasks(build_filters())["total"] == 8
        assert store.delete_samples() == 7
        assert [i["task_id"] for i in store.list_tasks(build_filters())["items"]] == ["real-1"]
    finally:
        store.close()


def test_result_links_are_only_returned_for_tier_a(tmp_path):
    seed(tmp_path, "user-a")
    store = open_store(tmp_path, "user-a")
    try:
        items = {i["task_id"]: i for i in store.list_tasks(build_filters())["items"]}
        assert items["sample-pr"]["result_url"].startswith("https://")
        assert items["sample-social"]["result_url"] is None
        detail = store.get_task("sample-social")
        assert detail["evidence"]["url"] is None
        assert store.get_task("sample-pr")["evidence"]["url"].startswith("https://")
    finally:
        store.close()
