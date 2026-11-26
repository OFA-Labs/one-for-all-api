import pytest

from ofa_execution.config import App, LocalConfig
from ofa_execution.contracts import ExecutionError
from voice.discovery import app_id


def test_packaged_identity_has_no_executable_prerequisite():
    app = App(name="Example", launch_kind="aumid", launch_identity="Example.App_12345!App")
    assert LocalConfig(apps=[app]).app("example").launch_kind == "aumid"


def test_duplicate_shortcuts_share_a_discovery_identity(tmp_path):
    first = App(name="Editor", executable=str(tmp_path/"Editor.exe"), launch_kind="shortcut", launch_identity="a.lnk")
    second = first.model_copy(update={"launch_identity": "b.lnk"})
    assert app_id(first) == app_id(second)


def test_packaged_window_readback_checks_identity_and_limits_ambiguity_to_open(monkeypatch):
    from ofa_execution import windows
    from ofa_execution import native_launch
    app = App(name="Example", launch_kind="aumid", launch_identity="Example.App_12345!App")
    items = [{"window": 1, "title": "Example", "pid": 11}, {"window": 2, "title": "Example", "pid": 22}]
    monkeypatch.setattr(windows, "windows", lambda: items)
    monkeypatch.setattr(windows, "process_identity", lambda pid: {"pid": pid, "executable": "app.exe", "started": 1})
    monkeypatch.setattr(native_launch, "application_identity", lambda pid: app.launch_identity)
    hand = windows.DesktopHand(LocalConfig(apps=[app]))
    assert hand._find(app, allow_multiple=True)["window"] == 1
    with pytest.raises(ExecutionError, match="More than one"):
        hand._find(app)
    monkeypatch.setattr(native_launch, "application_identity", lambda pid: "Different.App_12345!App")
    assert hand._find(app, allow_multiple=True) is None
