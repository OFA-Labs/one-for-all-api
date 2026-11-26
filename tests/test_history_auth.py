"""History auth: fail-closed tokens, member vs service, and the History error envelope."""
import json

from history.config import load_config
from history_support import (TOKEN_A, TOKEN_SVC, auth, make_client, seed, snapshot)


def test_unset_or_invalid_tokens_fail_closed(tmp_path):
    for raw in (None, "", "not json", "[]", '"x"', '{"t": "nope"}', '{"t": {"role": "member"}}',
                '{"t": {"role": "admin", "user": "u"}}', '{"": {"role": "service"}}'):
        env = {} if raw is None else {"HISTORY_TOKENS": raw}
        assert load_config(env)["tokens"] == {}, raw
    client = make_client(tmp_path, tokens={})
    assert client.get("/v1/tasks", headers=auth("anything")).status_code == 401


def test_load_config_reads_history_env_only():
    env = {"HISTORY_TOKENS": json.dumps({"m": {"user": "u", "role": "member"},
                                         "s": {"user": None, "role": "service"}}),
           "HISTORY_DATA_DIR": "/data/h", "HISTORY_CURSOR_SECRET": "sekret",
           "EBRAIN_TOKENS": '{"x": {}}', "EBRAIN_DATA_DIR": "/data/e"}
    cfg = load_config(env)
    assert cfg["tokens"] == {"m": {"user": "u", "role": "member"},
                             "s": {"user": None, "role": "service"}}
    assert cfg["data_dir"] == "/data/h"
    assert cfg["cursor_secret"] == b"sekret"


def test_missing_and_unknown_tokens_are_401_with_envelope(tmp_path):
    client = make_client(tmp_path)
    for headers in ({}, auth("nope"), {"Authorization": TOKEN_A}, {"Authorization": "Basic abc"},
                    {"Authorization": "Bearer "}):
        res = client.get("/v1/tasks", headers=headers)
        assert res.status_code == 401
        assert res.json() == {"error": {"code": "unauthorized",
                                        "message": "Missing or unknown bearer token."}}
        assert res.headers["cache-control"] == "private, no-store"


def test_authentication_is_checked_before_parameter_validation(tmp_path):
    client = make_client(tmp_path)
    assert client.get("/v1/tasks?limit=0&tz=bad").status_code == 401


def test_member_cannot_write_and_service_cannot_read(tmp_path):
    client = make_client(tmp_path)
    body = snapshot()
    res = client.post("/v1/tasks", json=body, headers=auth(TOKEN_A))
    assert res.status_code == 403 and res.json()["error"]["code"] == "forbidden"
    assert client.get("/v1/tasks", headers=auth(TOKEN_SVC)).status_code == 403
    assert client.post("/v1/tasks", json=body).status_code == 401
    assert client.post("/v1/tasks", json=body, headers=auth(TOKEN_SVC)).status_code == 201


def test_member_identity_comes_only_from_the_token(tmp_path):
    seed(tmp_path, "user-a")
    client = make_client(tmp_path)
    res = client.get("/v1/tasks?user_id=user-a&user=user-a", headers=auth("tok-b"))
    assert res.status_code == 200 and res.json()["total"] == 0
    assert client.get("/v1/tasks/sample-pr", headers=auth("tok-b")).status_code == 404
    assert client.get("/v1/tasks/sample-pr", headers=auth(TOKEN_A)).status_code == 200


def test_errors_never_echo_tokens_or_input(tmp_path, caplog):
    client = make_client(tmp_path)
    secret_goal = "my-very-private-goal-text"
    with caplog.at_level("DEBUG"):
        bad = client.get(f"/v1/tasks?q={secret_goal * 20}&limit=999", headers=auth(TOKEN_A))
        client.post("/v1/tasks", content=json.dumps(snapshot(goal=secret_goal, state="bogus")),
                    headers=auth(TOKEN_SVC))
        client.get("/v1/tasks", headers=auth("tok-wrong-secret-value"))
    assert bad.status_code == 400
    assert secret_goal not in bad.text
    # httpx/asyncio records come from the test client, not the server under test.
    server_logs = "\n".join(r.getMessage() for r in caplog.records
                            if r.name.split(".")[0] not in ("httpx", "httpcore", "asyncio"))
    assert secret_goal not in server_logs
    assert "tok-wrong-secret-value" not in server_logs and TOKEN_A not in server_logs
