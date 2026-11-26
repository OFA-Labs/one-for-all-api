"""Q1 vault server auth/loopback, V11 no values in responses, V12 dry-run; spoken controls and echo guard."""
import pytest
from fastapi.testclient import TestClient

from ofa.config import OfaConfig
from ofa.egress import EGRESS
from ofa.engine.fake import FakeEngine
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.runtime import build_core
from ofa.server import create_app
from ofa.speech.controls import control_of
from ofa.speech.echo import EchoGuard


class Yes:
    def verify(self, reason):
        return True


@pytest.fixture
def core(tmp_path, monkeypatch):
    monkeypatch.setenv("OFA_DATA_DIR", str(tmp_path))
    import ofa.vault.store as store
    monkeypatch.setattr(store, "dpapi_wrap", lambda k: k[::-1])
    monkeypatch.setattr(store, "dpapi_unwrap", lambda k: k[::-1])
    c = build_core(OfaConfig(engine="fake"), harness=Harness(FakeDesktop()), engine=FakeEngine(), verifier=Yes())
    c.vault._wrap, c.vault._unwrap = (lambda k: k[::-1]), (lambda k: k[::-1])
    yield c
    EGRESS.forget_all()


def client(core):
    app = create_app(core, token="T0K")
    return TestClient(app), {"authorization": "Bearer T0K"}


def test_health_open_vault_api_needs_token(core):
    c, h = client(core)
    assert c.get("/health").json()["ok"]
    assert c.get("/vault/api/items").status_code == 401
    assert c.get("/vault/api/items", headers={"authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/vault/api/items", headers=h).status_code == 200


def test_vault_api_never_returns_values(core):
    c, h = client(core)
    assert c.post("/vault/api/items", headers=h, json={"data_class": "D3", "service": "github", "label": "password",
                                                       "value": "Zz-Secret-998877"}).status_code == 423
    assert c.post("/vault/api/unlock", headers=h).json()["unlocked"]
    r = c.post("/vault/api/items", headers=h, json={"data_class": "D3", "service": "github", "label": "password",
                                                    "value": "Zz-Secret-998877", "allowed_targets": ["https://github.com"]})
    handle = r.json()["handle"]
    assert handle == "vault:D3/github/password#1"
    listing = c.get("/vault/api/items", headers=h).text + c.get("/health").text
    assert "Zz-Secret-998877" not in listing and handle in listing
    from urllib.parse import quote
    enc = quote(handle, safe="")
    assert c.post(f"/vault/api/items/{enc}/revoke", headers=h).json()["ok"]
    assert core.vault.meta(handle)["revoked"]
    assert c.delete(f"/vault/api/items/{enc}", headers=h).json()["ok"]
    assert core.vault.list(include_revoked=True) == []


def test_dry_run_fills_right_origin_refuses_lookalike(core):
    c, h = client(core)
    c.post("/vault/api/unlock", headers=h)
    c.post("/vault/api/items", headers=h, json={"data_class": "D3", "service": "ofa-mock", "label": "password",
                                                "value": "mock-pass-123", "allowed_targets": ["http://127.0.0.1:8768"]})
    r = c.post("/vault/api/dry-run", headers=h).json()
    assert r["verified_origin"]["ok"] and not r["lookalike"]["ok"]


def test_pages_are_served(core):
    c, _ = client(core)
    assert "Vault" in c.get("/vault").text and "Mock sign in" in c.get("/mock/login").text


def test_controls_and_echo_guard():
    assert control_of("Stop.") == "stop" and control_of("ruko") == "stop" and control_of("pause") == "pause"
    assert control_of("stop the music in spotify") is None
    guard = EchoGuard()
    guard.note("Completed. Anything else?")
    assert guard.is_echo("completed anything else") and not guard.is_echo("open whatsapp")
