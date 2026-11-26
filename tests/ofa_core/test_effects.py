"""Effect routing and the credential fill path against the fake desktop."""
import pytest

from ofa.effects import run_effect
from ofa.harness.api import Harness, HarnessError
from ofa.harness.fake import FakeDesktop
from ofa.memory import Memory
from ofa.policy import Action
from ofa.ports import VoicePort
from ofa.vault.broker import Broker


class StubVault:
    def meta(self, handle):
        return {"revoked": False, "allowed_targets": ["app:C:/Apps/app.exe"]}

    def reveal_for_broker(self, handle):
        return "effect-secret-123"


def rig(tmp_path):
    desk = FakeDesktop()
    harness = Harness(desk)
    return desk, harness, Memory(tmp_path / "m.db")


@pytest.mark.parametrize("target,opened", [
    ("https://example.com", "https://example.com"),
    ("example.com", "https://example.com"),
])
def test_open_routes_addresses_to_the_browser(tmp_path, target, opened):
    desk, harness, memory = rig(tmp_path)
    harness.open_url = lambda url: {"opened": url}
    result = run_effect(harness, memory, None, Action(verb="open", target=target, args={"op": "open"}))
    assert result["opened"] == opened


def test_open_routes_a_name_to_an_installed_app(tmp_path):
    desk, harness, memory = rig(tmp_path)
    run_effect(harness, memory, None, Action(verb="open", target="Notepad", args={"op": "open"}))
    assert desk.opened == ["Notepad"]


def test_fill_secret_reaches_the_field_and_returns_no_value(tmp_path):
    desk, harness, memory = rig(tmp_path)
    desk.add_window("App", "app.exe", [("Password", "edit", (0, 0, 50, 20))])
    harness.screen()
    action = Action(verb="fill", handle="vault:D3/app/password#1", args={"op": "fill_secret", "element": "u0"})
    result = run_effect(harness, memory, Broker(StubVault()), action)
    assert result == {"filled": True, "reason": "ok", "verified": True}
    assert "effect-secret-123" not in str(result)


def test_fill_secret_without_a_vault_is_refused(tmp_path):
    _, harness, memory = rig(tmp_path)
    result = run_effect(harness, memory, None, Action(verb="fill", args={"op": "fill_secret"}))
    assert result["reason"] == "VAULT_UNAVAILABLE"


def test_unknown_operation_is_an_error(tmp_path):
    _, harness, memory = rig(tmp_path)
    with pytest.raises(HarnessError):
        run_effect(harness, memory, None, Action(verb="x", args={"op": "frobnicate"}))


def test_voice_port_without_a_front_end_hears_nothing():
    import asyncio
    spoken = []
    port = VoicePort(lambda kind, **data: spoken.append(data["text"]))

    async def run():
        await port.speak("hello")
        return await port.listen(0.1), await port.listen_dictation(0.1)
    assert asyncio.run(run()) == (None, None) and spoken == ["hello"]
