"""System controls: the right policy tier for each, and the effects reach the desktop backend."""
import pytest

from ofa.effects import system
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.policy import Action, TurnLog, classify_tier
from ofa.tools import to_action


def action(control, value=None, turn="t"):
    return to_action("system", {"control": control, **({"value": value} if value is not None else {})}, turn)


@pytest.mark.parametrize("control,tier", [("volume_up", 1), ("mute", 1), ("play_pause", 1), ("lock", 1),
                                          ("brightness_set", 1), ("processes", 0), ("end_process", 2),
                                          ("clipboard_read", 2)])
def test_tiers(control, tier):
    assert classify_tier(action(control)) == tier


def test_clipboard_read_is_direct_only_when_the_user_said_clipboard():
    turns = TurnLog()
    turns.add("t", "read my clipboard", 0)
    assert classify_tier(action("clipboard_read"), turns, 0) == 1


def test_keys_and_volume_level_reach_the_backend():
    desk = FakeDesktop()
    h = Harness(desk)
    system.run_system(h, action("mute"))
    system.run_system(h, action("volume_set", "30"))
    assert desk.keys[0] == "volume_mute" and desk.keys.count("volume_down") == 50 and desk.keys.count("volume_up") == 15


def test_protected_processes_are_never_ended():
    assert system.run_system(Harness(FakeDesktop()), action("end_process", "lsass.exe"))["status"] == "refused"


def test_screenshot_is_masked_and_saved(tmp_path):
    desk = FakeDesktop()
    out = system.run_system(Harness(desk), action("screenshot_save", str(tmp_path / "shot")))
    assert out["verified"] and out["saved"].endswith("shot.png")


def test_unknown_control_is_a_bad_argument():
    from ofa.tools import ToolArgError
    with pytest.raises(ToolArgError):
        action("format_disk")
    assert Action(verb="system_control").verb
