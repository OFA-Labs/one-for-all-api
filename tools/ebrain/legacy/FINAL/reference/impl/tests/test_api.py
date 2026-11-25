"""HTTP contract (09-test-plan T-023, T-025, T-026, T-060, T-061, T-091, T-092). Needs the pinned
backend deps (FINAL/reference/requirements-backend.txt); skipped when fastapi is not installed."""
import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from ebrain.api import create_app  # noqa: E402

TOKENS = {"t-claude": {"user": "u-jai", "agent": "claude", "human": False},
          "t-codex": {"user": "u-jai", "agent": "codex", "human": False},
          "t-human": {"user": "u-jai", "agent": "human", "human": True},
          "t-other": {"user": "u-other", "agent": "claude", "human": False}}


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app({"data_dir": str(tmp_path), "tokens": TOKENS}))


def WB(op, ts, text, **kw):
    return {"op_id": op, "ts": ts, "visibility": kw.pop("visibility", "shared"),
            "kind": kw.pop("kind", "claim"), "text": text, **kw}


def current(client, tok, text, ts=100):
    r = client.post("/v1/ebrain/query", json={"ts": ts, "text": text}, headers=H(tok)).json()
    return [i["item_id"] for i in r["items"] if i["status"] == "current"]


def test_T025_fail_closed_without_tokens(tmp_path, monkeypatch):
    monkeypatch.delenv("EBRAIN_TOKENS", raising=False)
    c = TestClient(create_app({"data_dir": str(tmp_path)}))
    assert c.get("/v1/ebrain/limits", headers=H("t-claude")).status_code == 401
    import ebrain.api  # module-level app imports without EBRAIN_TOKENS
    assert ebrain.api.app is not None


def test_T060_missing_or_unknown_token_is_401(client):
    assert client.get("/v1/ebrain/limits").status_code == 401
    assert client.get("/v1/ebrain/limits", headers=H("nope")).status_code == 401


def test_T026_error_contract(client):
    bad_shape = client.post("/v1/ebrain/write", json={"op_id": "x", "ts": "not-int"},
                            headers=H("t-claude"))
    assert bad_shape.status_code == 422
    sem = client.post("/v1/ebrain/write", json=WB("x", 1, "", kind="bogus"), headers=H("t-claude"))
    assert sem.status_code == 200 and sem.json() == {"accepted": False, "reason": "bad kind"}
    ok = client.post("/v1/ebrain/write", json=WB("y", 1, "The OTP length is 6 (VC-APIA01).",
                                                  supersedes=["missing-op"]), headers=H("t-claude"))
    assert ok.json() == {"accepted": True, "reason": ""}


def test_T060_agent_from_token_not_body(client):
    body = WB("p1", 1, "The wake word is Jarvis (VC-APIP01).", visibility="private",
              agent_id="codex")  # extra field is ignored
    client.post("/v1/ebrain/write", json=body, headers=H("t-claude"))
    assert current(client, "t-claude", "wake word?") == ["p1"]
    assert current(client, "t-codex", "wake word?") == []
    assert current(client, "t-other", "wake word?") == []  # another user


def test_T061_human_only_routes_and_authority_downgrade(client):
    client.post("/v1/ebrain/write", json=WB("h1", 1, "The Vercel plan is Pro (VC-APIH01).",
                                             authority="human"), headers=H("t-claude"))
    client.post("/v1/ebrain/write", json=WB("g1", 2, "The Vercel plan is Hobby (VC-APIH02)."),
                headers=H("t-codex"))
    assert current(client, "t-claude", "Vercel plan?") == ["g1"]  # h1 was stored as agent
    for path, body in (("/v1/ebrain/rollback", {"to_ts": 0}),
                       ("/v1/ebrain/heal/h1/approve", {"ts": 3}),
                       ("/v1/ebrain/pairs/confirm", {"a": "x", "b": "y", "ts": 3}),
                       ("/v1/ebrain/resolve", {"chain": "x", "pick_op_id": "h1", "ts": 3})):
        assert client.post(path, json=body, headers=H("t-claude")).status_code == 403
    assert client.post("/v1/ebrain/heal/h1/approve", json={"ts": 3},
                       headers=H("t-human")).status_code == 404


def test_T023_limits_merges_facts_with_default_project(client):
    client.post("/v1/ebrain/write", json=WB("a", 1, "The OTP length is 6 (VC-APIL01)."),
                headers=H("t-claude"))
    d = client.get("/v1/ebrain/limits", headers=H("t-human")).json()
    assert d["memory_count"] == 1 and d["capacity_state"] == "ok" and d["capacity_hard"] == 1000
    assert d["schema_version"] == 1 and d["copy"]["experimental_badge"] == "EXPERIMENTAL"
    assert {c["id"] for c in d["capabilities"]} >= {"latest_wins", "reworded_split"}


def test_T027_resolve_conflict_by_human(client):
    client.post("/v1/ebrain/write", json=WB("c1", 5, "The OTP length is 4 (VC-APIC01)."),
                headers=H("t-claude"))
    client.post("/v1/ebrain/write", json=WB("c2", 5, "The OTP length is 8 (VC-APIC02)."),
                headers=H("t-codex"))
    assert current(client, "t-claude", "OTP length?") == []
    chain = client.get("/v1/ebrain/chains", headers=H("t-human")).json()["chains"][0]["chain"]
    r = client.post("/v1/ebrain/resolve", json={"chain": chain, "pick_op_id": "c2", "ts": 6},
                    headers=H("t-human")).json()
    assert r["accepted"] and current(client, "t-claude", "OTP length?") == [r["op_id"]]


def test_T091_delete_me(client):
    client.post("/v1/ebrain/write", json=WB("a", 1, "The OTP length is 6 (VC-APID01)."),
                headers=H("t-claude"))
    client.post("/v1/ebrain/write", json=WB("b", 1, "The OTP length is 7 (VC-APID02)."),
                headers=H("t-other"))
    assert client.delete("/v1/ebrain/me", headers=H("t-claude")).json()["deleted_rows"] >= 1
    assert client.get("/v1/ebrain/limits", headers=H("t-human")).json()["memory_count"] == 0
    assert client.get("/v1/ebrain/limits", headers=H("t-other")).json()["memory_count"] == 1


def test_T092_no_secret_echo(client):
    secret = "sk-abcdefghijklmnop1234"
    client.post("/v1/ebrain/write", json=WB("s", 1, f"The deploy region is eu-west-1 (VC-APIS01). "
                                             f"api_key={secret}"), headers=H("t-claude"))
    q = client.post("/v1/ebrain/query", json={"ts": 9, "text": "deploy region?"}, headers=H("t-claude"))
    ch = client.get("/v1/ebrain/chains", headers=H("t-claude")).json()["chains"][0]["chain"]
    v = client.get(f"/v1/ebrain/chains/{ch}", headers=H("t-claude"))
    assert secret not in q.text and secret not in v.text
