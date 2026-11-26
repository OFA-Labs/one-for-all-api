"""The combined app: E-Brain unchanged, History mounted, separate configs, /healthz."""
from history_support import TOKEN_A, auth, history_config, make_app, make_client, seed
from fastapi.testclient import TestClient

from oneforall.api import create_app

EBRAIN_TOKEN = "eb-token"


def ebrain_client(tmp_path):
    app = create_app(
        {"data_dir": str(tmp_path / "ebrain"),
         "tokens": {EBRAIN_TOKEN: {"user": "eb-user", "agent": "claude", "human": False}}},
        history_config(tmp_path))
    return TestClient(app)


def test_ebrain_routes_still_work_and_history_is_mounted(tmp_path):
    seed(tmp_path, "user-a")
    client = ebrain_client(tmp_path)
    limits = client.get("/v1/ebrain/limits", headers=auth(EBRAIN_TOKEN))
    assert limits.status_code == 200 and "capacity_state" in limits.json()
    assert client.get("/v1/tasks", headers=auth(TOKEN_A)).json()["total"] == 7


def test_ebrain_error_shapes_are_unchanged(tmp_path):
    client = ebrain_client(tmp_path)
    unauth = client.get("/v1/ebrain/limits")
    assert unauth.status_code == 401
    assert unauth.json() == {"detail": "missing or unknown bearer token"}
    invalid = client.post("/v1/ebrain/query", json={"ts": "not-a-number"},
                          headers=auth(EBRAIN_TOKEN))
    assert invalid.status_code == 422 and isinstance(invalid.json()["detail"], list)
    assert client.get("/nope").json() == {"detail": "Not Found"}
    # ...while History routes use their own envelope
    assert "error" in client.get("/v1/tasks?limit=0", headers=auth(TOKEN_A)).json()


def test_the_two_configs_do_not_leak_into_each_other(tmp_path):
    client = ebrain_client(tmp_path)
    # a History token is not an E-Brain token, and vice versa
    assert client.get("/v1/ebrain/limits", headers=auth(TOKEN_A)).status_code == 401
    assert client.get("/v1/tasks", headers=auth(EBRAIN_TOKEN)).status_code == 401
    # each store keeps its own database under its own directory
    seed(tmp_path, "user-a")
    client.get("/v1/ebrain/limits", headers=auth(EBRAIN_TOKEN))
    assert (tmp_path / "history" / "history.sqlite").exists()
    assert (tmp_path / "ebrain" / "ebrain.sqlite").exists()


def test_healthz_is_public_and_reports_both_stores(tmp_path):
    body = make_client(tmp_path).get("/healthz")
    assert body.status_code == 200
    assert body.json() == {"ok": True, "ebrain": "ok", "history": "ok", "history_schema": 1}


def test_healthz_reports_unavailability_without_details(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory")
    app = create_app({"data_dir": str(tmp_path / "ebrain"), "tokens": {}},
                     {**history_config(tmp_path), "data_dir": str(blocker / "history")})
    res = TestClient(app).get("/healthz")
    assert res.status_code == 503
    assert res.json() == {"ok": False, "ebrain": "ok", "history": "unavailable"}
    assert str(blocker) not in res.text


def test_cors_is_inherited_for_the_local_web_origins(tmp_path):
    client = make_client(tmp_path)
    ok = client.options("/v1/tasks", headers={"Origin": "http://127.0.0.1:3000",
                                              "Access-Control-Request-Method": "GET",
                                              "Access-Control-Request-Headers": "authorization"})
    assert ok.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
    bad = client.options("/v1/tasks", headers={"Origin": "https://evil.example",
                                               "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in bad.headers


def test_module_level_app_imports_without_any_environment():
    import oneforall.api as module
    assert module.app.title == "E-Brain"
