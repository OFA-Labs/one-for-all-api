"""Settings → Eyes / Hands / Voice over the companion API: paired pages only, validated, nothing secret."""
import io

import pytest
from fastapi.testclient import TestClient

from ofa.config import OfaConfig
from ofa.engine.fake import FakeEngine
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.runtime import build_core
from voice.api import create_app
from voice.config import Settings
from voice.events import Events

ORIGIN = "http://127.0.0.1:3000"


class Pairing:
    def authorize(self, origin, token):
        if token != "paired":
            raise PermissionError("not paired")
        return {}


class Brain:
    def __init__(self, core):
        self.core = core


class Session:
    def __init__(self, brain):
        self.brain = brain


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("OFA_DATA_DIR", str(tmp_path))
    desk = FakeDesktop()
    desk.add_window("OFA Execution Test Pad", "python.exe", [("Apply", "button", (20, 100, 120, 135))])
    core = build_core(OfaConfig(engine="fake"), harness=Harness(desk), engine=FakeEngine())
    app = create_app(Settings(), Events("fake", io.StringIO()), Session(Brain(core)), "x" * 48, Pairing())
    with TestClient(app, base_url="http://127.0.0.1:8767") as c:
        yield c, core


def call(c, method, path, token="paired", json=None):
    headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
    return c.post(path, headers=headers, json=json or {}) if method == "post" else c.get(path, headers=headers)


def test_unpaired_pages_get_nothing(client):
    c, _ = client
    assert call(c, "get", "/v1/ofa/settings", token="nope").status_code == 403
    assert call(c, "post", "/v1/eyes/preview", token="nope").status_code == 403


def test_read_and_save_settings(client):
    c, core = client
    body = call(c, "get", "/v1/ofa/settings").json()
    assert body["settings"]["eyes"]["mode"] == "local" and body["always_ask"]
    saved = call(c, "post", "/v1/ofa/settings", json={"eyes": {"mode": "reasoning"}, "hands": {"answer_calls": False}})
    assert saved.status_code == 200
    assert saved.json()["eyes"]["active"] == "local" and saved.json()["eyes"]["note"]   # the fake engine cannot see
    assert core.deps.settings.get().hands.answer_calls is False


@pytest.mark.parametrize("patch", [{"eyes": {"mode": "x-ray"}}, {"brain": {"model": "x"}}, {"eyes": {"model": "a b"}},
                                   {"eyes": {"unknown": 1}}])
def test_invalid_settings_are_refused(client, patch):
    c, core = client
    assert call(c, "post", "/v1/ofa/settings", json=patch).json()["code"] == "INVALID_SETTINGS"
    assert core.deps.settings.get().eyes.mode == "local"


def test_eyes_preview_is_masked_and_not_sent(client):
    c, _ = client
    body = call(c, "post", "/v1/eyes/preview").json()
    assert body["image"].startswith("data:image/png;base64,") and body["sent_anywhere"] is False
    assert body["marks"] == 1 and "masked" in body["masked"]


def test_health_reports_eyes_mode(client):
    c, _ = client
    speech = c.get("/v1/health").json()["speech"]
    assert speech["eyes_mode"] == "local" and speech["eyes_ready"] is True
