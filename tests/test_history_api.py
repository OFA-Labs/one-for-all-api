"""History HTTP contract: list, detail, export, envelope, tenancy and no leakage."""
import json

import pytest

from history_support import TOKEN_A, TOKEN_B, auth, make_client, seed


@pytest.fixture
def client(tmp_path):
    seed(tmp_path, "user-a")
    seed(tmp_path, "user-b")
    return make_client(tmp_path)


def get(client, path, token=TOKEN_A):
    return client.get(path, headers=auth(token))


def test_list_returns_the_documented_shape(client):
    res = get(client, "/v1/tasks?limit=3")
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"items", "next_cursor", "total"}
    assert body["total"] == 7 and len(body["items"]) == 3 and body["next_cursor"]
    assert set(body["items"][0]) == {
        "task_id", "title", "subtitle", "goal", "scenario", "state", "display_status", "tier",
        "evidence_status", "occurred_at", "duration_ms", "is_sample", "result_url", "summary"}
    first = body["items"][0]
    assert first["task_id"] == "sample-pr" and first["display_status"] == "Verified"
    assert first["is_sample"] is True and first["duration_ms"] == 45 * 60_000
    assert res.headers["cache-control"] == "private, no-store"
    assert "Authorization" in res.headers["vary"]


def test_list_filters(client):
    ids = lambda qs: [i["task_id"] for i in get(client, "/v1/tasks?" + qs).json()["items"]]
    assert ids("status=Verified") == ["sample-pr", "sample-research"]
    assert ids("state=paused") == ["sample-paused"]
    assert ids("tier=B") == ["sample-social"]
    assert ids("q=PR%20%23142") == ["sample-pr"]
    assert ids("sort=oldest&limit=2") == ["sample-unknown", "sample-paused"]
    assert ids("from=2026-11-15&to=2026-11-16&tz=Asia/Kolkata") == [
        "sample-research", "sample-social", "sample-refusal"]
    assert ids("include_sample=0") == []


def test_detail_shape_and_content(client):
    body = get(client, "/v1/tasks/sample-pr").json()
    assert set(body) == {"task", "plan", "events", "event_count", "evidence", "ledger",
                         "approvals", "artifacts"}
    assert body["task"]["display_status"] == "Verified" and body["task"]["revision"] == 1
    assert body["plan"]["steps"][0].startswith("Read PR #142")
    assert body["plan"]["sites"] == ["github.com", "slack.com"]
    assert body["plan"]["recipients"] == ["#engineering"]
    assert body["plan"]["hash"].startswith("sha256:") and body["plan"]["version"] == 1
    assert [e["seq"] for e in body["events"]] == list(range(1, 8)) == [
        e["seq"] for e in body["events"]]
    assert body["event_count"] == 7
    assert body["evidence"]["tier"] == "A" and body["evidence"]["url"]
    ledger = body["ledger"][0]
    assert ledger["state"] == "verified"
    assert [(t["from"], t["to"]) for t in ledger["transitions"]] == [
        (None, "intent"), ("intent", "committed"), ("committed", "verified")]
    assert body["approvals"][0]["decision"] == "approved"
    assert body["artifacts"] == []


def test_honesty_cases_in_detail(client):
    unknown = get(client, "/v1/tasks/sample-unknown").json()
    assert unknown["task"]["display_status"] == "Unknown"
    assert unknown["ledger"][0]["state"] == "intent"
    assert unknown["approvals"][0]["decision"] == "expired"
    social = get(client, "/v1/tasks/sample-social").json()
    assert social["task"]["display_status"] == "Submitted"
    assert social["evidence"]["url"] is None
    assert [r["state"] for r in social["ledger"]] == ["committed"] * 3
    refusal = get(client, "/v1/tasks/sample-refusal").json()
    assert refusal["evidence"] is None and refusal["ledger"] == []


def test_missing_and_malformed_ids_are_404(client):
    for path in ("/v1/tasks/nope", "/v1/tasks/nope/export", "/v1/tasks/..%2Fx", "/v1/tasks/%2E%2E",
                 "/v1/tasks/%2e", "/v1/tasks/-x",
                 "/v1/tasks/has space", "/v1/tasks/" + "a" * 200):
        res = get(client, path)
        assert res.status_code == 404, path
        assert res.json()["error"]["code"] == "not_found"


def test_another_users_task_and_export_are_404_not_403(tmp_path):
    seed(tmp_path, "user-a")  # user-b has no rows at all
    client = make_client(tmp_path)
    assert get(client, "/v1/tasks/sample-pr", TOKEN_A).status_code == 200
    for path in ("/v1/tasks/sample-pr", "/v1/tasks/sample-pr/export"):
        res = get(client, path, TOKEN_B)
        assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    assert get(client, "/v1/tasks", TOKEN_B).json()["total"] == 0


def test_unknown_route_and_method_use_the_envelope(client):
    res = get(client, "/v1/tasks/sample-pr/events")
    assert res.status_code == 404 and res.json()["error"]["code"] == "not_found"
    res = client.delete("/v1/tasks/sample-pr", headers=auth(TOKEN_A))
    assert res.status_code == 405 and "error" in res.json()


@pytest.mark.parametrize("qs", ["limit=0", "limit=51", "limit=abc", "tz=Mars/Base",
                                "status=Bogus", "sort=random", "from=2026-1-1",
                                "cursor=garbage", "include_sample=9", "q=" + "a" * 201])
def test_bad_parameters_are_400_with_the_envelope(client, qs):
    res = get(client, "/v1/tasks?" + qs)
    assert res.status_code == 400, qs
    assert set(res.json()) == {"error"}
    assert set(res.json()["error"]) == {"code", "message"}
    assert "detail" not in res.json()


def test_error_codes(client):
    assert get(client, "/v1/tasks?tz=Mars/Base").json()["error"]["code"] == "invalid_timezone"
    assert get(client, "/v1/tasks?cursor=garbage").json()["error"]["code"] == "invalid_cursor"
    assert get(client, "/v1/tasks?from=2026-12-01&to=2026-11-01").json()["error"][
        "code"] == "invalid_range"
    assert get(client, "/v1/tasks?limit=0").json()["error"]["code"] == "invalid_param"


def test_export_is_a_json_attachment_without_secrets(client):
    res = get(client, "/v1/tasks/sample-pr/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert res.headers["content-disposition"] == 'attachment; filename="sample-pr.json"'
    assert res.headers["cache-control"] == "private, no-store"
    body = json.loads(res.text)
    assert set(body) == {"schema_version", "exported_at", "notice", "task", "plan", "events",
                         "evidence", "ledger", "approvals"}
    assert body["schema_version"] == 1 and "Screenshots are not included" in body["notice"]
    assert body["task"]["task_id"] == "sample-pr"
    for forbidden in ("storage_key", "storage_path", TOKEN_A, TOKEN_B, "tok-svc", "user-a",
                      "content_hash", "search_text"):
        assert forbidden not in res.text, forbidden
    assert get(client, "/v1/tasks/sample-pr/export", token=TOKEN_B).status_code == 200


def test_responses_never_contain_internal_columns(client):
    for path in ("/v1/tasks", "/v1/tasks/sample-pr", "/v1/history/calendar?from=2026-11-01&to=2026-12-01",
                 "/v1/history/period?from=2026-11-01&to=2026-11-30"):
        text = get(client, path).text
        for forbidden in ("storage_key", "content_hash", "search_text", "user_id", "plan_json"):
            assert forbidden not in text, (path, forbidden)
