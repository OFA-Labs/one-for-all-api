"""POST /v1/tasks: service-only upsert with revisions, conflicts and validation."""
import json
import sqlite3
from pathlib import Path

import pytest

from history_support import TOKEN_A, TOKEN_B, TOKEN_SVC, auth, make_client, open_store, snapshot

T0 = 1_763_278_200_000


@pytest.fixture
def client(tmp_path):
    return make_client(tmp_path)


def post(client, body, token=TOKEN_SVC):
    return client.post("/v1/tasks", json=body, headers=auth(token))


def read(client, task_id="task-1", token=TOKEN_A):
    return client.get(f"/v1/tasks/{task_id}", headers=auth(token))


def paused(**kw):
    return snapshot(state="paused", ended_at=None, **kw)


def test_create_then_read_back(client):
    res = post(client, snapshot(title="Hello", subtitle="Sub", goal="Goal text"))
    assert res.status_code == 201
    assert res.json() == {"created": True, "updated": False, "revision": 1}
    detail = read(client).json()
    assert detail["task"]["title"] == "Hello" and detail["task"]["display_status"] == "Declined"
    assert detail["task"]["duration_ms"] == 240_000
    assert detail["plan"]["hash"].startswith("sha256:")
    assert res.headers["cache-control"] == "private, no-store"


def test_server_ignores_client_supplied_display_status(client):
    body = snapshot(state="completed", tier="D", evidence_status="submitted")
    body["display_status"] = "Verified"
    assert post(client, body).status_code == 400  # unknown field (extra=forbid)
    del body["display_status"]
    assert post(client, body).status_code == 201
    assert read(client).json()["task"]["display_status"] == "Unknown"


def test_replay_is_a_noop(client):
    body = snapshot()
    assert post(client, body).status_code == 201
    again = post(client, body)
    assert again.status_code == 200
    assert again.json() == {"created": False, "updated": False, "revision": 1}


def test_same_revision_different_content_conflicts(client):
    assert post(client, snapshot(title="one")).status_code == 201
    res = post(client, snapshot(title="two"))
    assert res.status_code == 409 and res.json()["error"]["code"] == "conflict"
    assert read(client).json()["task"]["title"] == "one"


def test_non_terminal_task_can_advance_by_revision(client):
    assert post(client, paused(revision=1, title="Draft")).status_code == 201
    completed = snapshot(revision=2, title="Finished", state="completed", tier="B",
                         evidence_status="submitted", occurred_at=T0 + 5_000_000,
                         evidence={"tier": "B", "status": "submitted", "readback": "ok"})
    res = post(client, completed)
    assert res.status_code == 200 and res.json() == {"created": False, "updated": True,
                                                     "revision": 2}
    task = read(client).json()["task"]
    assert (task["revision"], task["title"], task["display_status"]) == (2, "Finished",
                                                                         "Submitted")
    assert task["occurred_at"] == T0 + 5_000_000  # occurred_at may move forward on a revision
    # children are replaced wholesale, not appended
    assert read(client).json()["event_count"] == 1


def test_stale_and_terminal_revisions_are_rejected(client):
    assert post(client, paused(revision=3)).status_code == 201
    assert post(client, paused(revision=2, title="stale")).status_code == 409
    assert post(client, snapshot(revision=4)).status_code == 200  # paused -> declined
    res = post(client, snapshot(revision=5, title="rewrite"))
    assert res.status_code == 409  # terminal tasks are never rewritten
    assert read(client).json()["task"]["revision"] == 4


APPROVAL = {"approval_id": "ap-1", "page_url": "https://x.test/", "plan_version": 1,
            "payload_hash": "sha256:p", "exact_text": "Send it.", "decision": "approved",
            "decided_at": T0}


def test_a_revision_cannot_drop_or_change_an_approval(client):
    assert post(client, paused(approvals=[APPROVAL])).status_code == 201
    assert post(client, paused(revision=2, approvals=[])).status_code == 409
    changed = {**APPROVAL, "exact_text": "Something else."}
    assert post(client, paused(revision=2, approvals=[changed])).status_code == 409
    keep = post(client, paused(revision=2, title="kept", approvals=[APPROVAL, {
        **APPROVAL, "approval_id": "ap-2", "decision": "revoked", "decided_at": T0 + 1}]))
    assert keep.status_code == 200
    assert [a["approval_id"] for a in read(client).json()["approvals"]] == ["ap-1", "ap-2"]


def test_invalid_snapshots_are_400(client):
    verified_no_evidence = snapshot(state="completed", tier="A", evidence_status="verified")
    tier_d_verified = snapshot(state="completed", tier="D", evidence_status="verified")
    mismatch = snapshot(state="completed", tier="B", evidence_status="submitted",
                        evidence={"tier": "A", "status": "verified"})
    for body in (snapshot(state="planning"), snapshot(state="executing"), snapshot(state="x"),
                 verified_no_evidence, tier_d_verified, mismatch,
                 snapshot(ended_at=T0 - 1), snapshot(task_id="bad id"), snapshot(task_id="a/b"), snapshot(task_id=".."),
                 snapshot(task_id="."), snapshot(task_id="-x"),
                 snapshot(title=""), snapshot(user_id=""), snapshot(revision=0),
                 snapshot(events=[{"seq": 1, "at": 1, "type": "a", "message": "x"},
                                  {"seq": 1, "at": 2, "type": "b", "message": "y"}]),
                 snapshot(approvals=[APPROVAL, APPROVAL]),
                 snapshot(ledger=[{"idempotency_key": "k", "site": "s", "action": "a",
                                   "payload_hash": "h", "state": "intent"}] * 2),
                 snapshot(plan={"steps": ["x"] * 51}),
                 snapshot(tier="Z")):
        res = post(client, body)
        assert res.status_code == 400, body
        assert res.json()["error"]["code"] == "invalid_param"
    assert client.get("/v1/tasks", headers=auth(TOKEN_A)).json()["total"] == 0


def test_malformed_and_oversized_bodies(client):
    for raw in (b"", b"not json", b"[]", b'{"task_id": "x"}'):
        res = client.post("/v1/tasks", content=raw, headers=auth(TOKEN_SVC))
        assert res.status_code == 400, raw
    huge = snapshot(goal="g" * 100, events=[
        {"seq": n, "at": 1, "type": "t", "message": "m" * 900} for n in range(1, 400)])
    res = client.post("/v1/tasks", content=json.dumps(huge), headers=auth(TOKEN_SVC))
    assert res.status_code == 413 and res.json()["error"]["code"] == "invalid_param"


def test_ingest_for_another_user_never_conflicts_or_leaks(client):
    assert post(client, snapshot(user="user-a", title="mine")).status_code == 201
    assert post(client, snapshot(user="user-b", title="theirs")).status_code == 201
    assert read(client, token=TOKEN_A).json()["task"]["title"] == "mine"
    assert read(client, token=TOKEN_B).json()["task"]["title"] == "theirs"


def test_an_approval_id_already_used_by_another_task_is_a_conflict(client):
    assert post(client, snapshot(task_id="t1", approvals=[APPROVAL])).status_code == 201
    res = post(client, snapshot(task_id="t2", approvals=[APPROVAL]))
    assert res.status_code == 409
    assert client.get("/v1/tasks/t2", headers=auth(TOKEN_A)).status_code == 404  # rolled back


def test_ledger_transitions_keep_their_order_even_with_equal_timestamps(client):
    ledger = [{"idempotency_key": "k", "site": "slack.com", "action": "send", "payload_hash": "h",
               "state": "verified", "transitions": [
                   {"to": "intent", "at": 5}, {"from": "intent", "to": "committed", "at": 5},
                   {"from": "committed", "to": "verified", "at": 5}]}]
    assert post(client, snapshot(ledger=ledger)).status_code == 201
    moves = read(client).json()["ledger"][0]["transitions"]
    assert [(t["seq"], t["from"], t["to"]) for t in moves] == [
        (1, None, "intent"), (2, "intent", "committed"), (3, "committed", "verified")]


def test_approvals_table_rejects_updates(tmp_path, client):
    assert post(client, snapshot(approvals=[APPROVAL])).status_code == 201
    store = open_store(tmp_path, "user-a")
    try:
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            store.db.execute("UPDATE approvals SET decision = 'rejected'")
        assert store.get_task("task-1")["approvals"][0]["decision"] == "approved"
    finally:
        store.close()


def test_history_lists_only_stable_states(client):
    for n, state in enumerate(["waiting", "permission", "question", "paused", "completed",
                               "declined", "cancelled", "error", "unknown"]):
        body = snapshot(task_id=f"t-{state}", state=state)
        if state == "completed":
            body.update(tier="B", evidence_status="submitted")
        assert post(client, body).status_code == 201
    got = client.get("/v1/tasks?limit=50", headers=auth(TOKEN_A)).json()
    assert got["total"] == 9
    assert {i["display_status"] for i in got["items"]} == {
        "Needs review", "Paused", "Submitted", "Declined", "Cancelled", "Error", "Unknown"}


def test_database_file_stays_inside_the_data_dir(tmp_path, client):
    post(client, snapshot())
    files = sorted(p.name for p in Path(tmp_path / "history").iterdir())
    assert "history.sqlite" in files
