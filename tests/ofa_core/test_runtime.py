"""Q1 server auth/loopback, V11 no values in responses, V12 dry-run; S1/S3/S5/S7/B7 voice loop."""
import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from ofa.config import OfaConfig
from ofa.egress import EGRESS
from ofa.engine.fake import FakeEngine
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.policy.approval import Heard
from ofa.runtime import build_core
from ofa.server import create_app
from ofa.speech.loop import EchoGuard, VoiceLoop, control_of


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
    app = create_app(core, None, token="T0K")
    return TestClient(app), {"authorization": "Bearer T0K"}


def test_health_open_status_needs_token(core):
    c, h = client(core)
    assert c.get("/health").json()["ok"]
    assert c.get("/status").status_code == 401
    assert c.get("/status", headers={"authorization": "Bearer wrong"}).status_code == 401
    assert c.get("/status", headers=h).status_code == 200


def test_vault_api_never_returns_values(core):
    c, h = client(core)
    assert c.post("/vault/api/items", headers=h, json={"data_class": "D3", "service": "github", "label": "password",
                                                       "value": "Zz-Secret-998877"}).status_code == 423
    assert c.post("/vault/api/unlock", headers=h).json()["unlocked"]
    r = c.post("/vault/api/items", headers=h, json={"data_class": "D3", "service": "github", "label": "password",
                                                    "value": "Zz-Secret-998877", "allowed_targets": ["https://github.com"]})
    handle = r.json()["handle"]
    assert handle == "vault:D3/github/password#1"
    listing = c.get("/vault/api/items", headers=h).text + c.get("/status", headers=h).text
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


def test_typed_command_runs_and_memory_delete(core):
    c, h = client(core)
    core.engine.script = [[__import__("ofa.engine.fake", fromlist=["x"]).tool("finish", status="done", summary="Hi")]]
    assert c.post("/command", headers=h, json={"text": "hello"}).json()["status"] == "done"
    core.memory.remember("my manager", "Priya")
    assert c.delete("/memory/my manager", headers=h).json()["deleted"]
    assert c.get("/audit", headers=h).json()["chain_ok"]
    assert "Vault" in c.get("/vault").text and "Mock sign in" in c.get("/mock/login").text


# --- voice loop ---------------------------------------------------------------------------------
class Dev:
    def __init__(self):
        self.started = self.closed = 0
        self.q = asyncio.Queue()

    def start(self):
        self.started += 1

    def close(self):
        self.closed += 1

    def interrupt(self):
        return 0

    async def read(self):
        return await self.q.get()


class Settings:
    headphones, rms_threshold, max_utterance_seconds, silence_ms, cooldown_seconds = False, 500, 20, 700, 30


class Speech:
    def __init__(self):
        self.said = []

    async def say(self, text, lang, playback, started):
        self.said.append(text)
        return True


def make_loop():
    turns, states = [], []
    sp = Speech()

    async def on_turn(h):
        turns.append(h.text)
        await asyncio.sleep(0.05)
    loop = VoiceLoop(Settings(), {}, lambda l, m: [], sp, Dev(), Dev(), lambda s, c=None, mic=None: states.append(s),
                     on_turn)
    return loop, turns, states, sp


def test_caps_toggles_and_kill_switch_bumps_epoch():
    async def run():
        loop, turns, states, _ = make_loop()
        epochs = []
        loop.on_epoch = epochs.append
        await loop.toggle()
        assert loop.active and states[-1] == "listening"
        await loop.dispatch(Heard("open notepad"))
        await asyncio.sleep(0.1)
        await loop.dispatch(Heard("now open slack"))
        await asyncio.sleep(0.1)
        assert turns == ["open notepad", "now open slack"] and loop.active      # multi-turn, completion doesn't end
        await loop.toggle()
        assert not loop.active and states[-1] == "idle" and len(set(epochs)) == 2
    asyncio.run(run())


def test_echo_dropped_and_control_stop_cancels_task():
    async def run():
        loop, turns, _, sp = make_loop()
        await loop.start()
        await loop.speak("I'm about to send the message to Asha. Should I go ahead?")
        await loop.dispatch(Heard("send the message to Asha should I go ahead", echo=loop.echo.is_echo(
            "send the message to Asha should I go ahead")))
        assert turns == []
        slow = asyncio.Event()

        async def long_turn(h):
            await slow.wait()
        loop.on_turn = long_turn
        await loop.dispatch(Heard("do a long thing"))
        e0 = loop.epoch
        await loop.dispatch(Heard("ruko"))
        await asyncio.sleep(0.01)
        assert loop.turn.cancelled() or loop.turn.done()
        assert loop.epoch == e0 + 1 and "Stopped." in sp.said
        await loop.stop()
    asyncio.run(run())


def test_answers_go_to_pending_listener_not_new_turn():
    async def run():
        loop, turns, _, _ = make_loop()
        await loop.start()

        async def answer():
            await asyncio.sleep(0.02)
            await loop.dispatch(Heard("haan bhej do"))
        asyncio.create_task(answer())
        heard = await loop.listen(1.0)
        assert heard.text == "haan bhej do" and turns == []
        assert await loop.listen(0.05) is None          # silence → None, never an approval
        await loop.stop()
    asyncio.run(run())


def test_correction_replaces_running_task():
    async def run():
        loop, turns, _, _ = make_loop()
        gate = asyncio.Event()

        async def on_turn(h):
            turns.append(h.text)
            await gate.wait()
        loop.on_turn = on_turn
        await loop.start()
        await loop.dispatch(Heard("open slack"))
        await asyncio.sleep(0.01)
        first = loop.turn
        await loop.dispatch(Heard("no, open discord"))
        await asyncio.sleep(0.01)
        assert first.cancelled() and turns == ["open slack", "no, open discord"]
        await loop.stop()
    asyncio.run(run())


def test_controls_and_echo_guard():
    assert control_of("Stop.") == "stop" and control_of("ruko") == "stop" and control_of("pause") == "pause"
    assert control_of("stop the music in spotify") is None
    g = EchoGuard()
    g.note("Completed. Anything else?")
    assert g.is_echo("completed anything else") and not g.is_echo("open whatsapp")
