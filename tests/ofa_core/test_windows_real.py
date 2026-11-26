"""H1/H2/H6/H8/V4 on the real desktop — only against windows this test launches itself."""
import subprocess
import sys
import time

import pytest

from ofa.harness.api import Harness

pytestmark = pytest.mark.windows


TITLE = "OFA Execution Test Pad"


def launch_pad(*flags):
    """Start a disposable pad and return (harness, hwnd, proc) for the NEW window only."""
    h = Harness()
    before = {w["hwnd"] for w in h.b.list_windows()}
    proc = subprocess.Popen([sys.executable, "-m", "ofa_execution.testpad", *flags], creationflags=0x00000008)
    for _ in range(80):
        time.sleep(0.1)
        new = [w["hwnd"] for w in h.b.list_windows() if w["hwnd"] not in before and w["title"] == TITLE]
        if new:
            return h, new[0], proc
    proc.kill()
    raise AssertionError("test pad did not open")


def close_pad(h, hwnd, proc):
    if h.b.window_exists(hwnd):
        h.b.close_window(hwnd)
    proc.kill()


@pytest.fixture
def pad():
    h, hwnd, proc = launch_pad()
    yield h, hwnd
    close_pad(h, hwnd, proc)


def test_discovery_lists_installed_and_running_apps():
    from ofa.harness import win
    apps = win.installed_apps(refresh=True)
    assert len(apps) > 10 and any(a.get("appid") for a in apps)
    assert Harness().windows()


def test_type_click_readback_on_unadapted_app(pad):
    h, hwnd = pad
    s = h.screen(hwnd)
    assert s["count"] >= 3 and "uia" in s["sources"]
    edit = next(line.split()[0] for line in s["elements"] if " edit" in line)
    r = h.type_text("नमस्ते OFA 42", edit)
    assert r["readback"] == "नमस्ते OFA 42"
    apply_btn = next(line.split()[0] for line in s["elements"] if '"Apply"' in line)
    c = h.click(apply_btn)
    assert c["verified"]
    assert h.wait_for_text("Result: नमस्ते OFA 42", hwnd, timeout=3)["found"]


def test_focus_minimize_restore_close_verified(pad):
    h, hwnd = pad
    assert h.focus(hwnd)["verified"]
    assert h.window_op(hwnd, "minimize")["verified"]
    assert h.window_op(hwnd, "restore")["verified"]
    assert h.window_op(hwnd, "close")["verified"]


def test_ocr_reads_window_text(pad):
    h, hwnd = pad
    h.focus(hwnd)
    s = h.screen(hwnd, ocr=True)
    assert "ocr" in s["sources"]
    assert any("Apply" in line or "Input" in line for line in s["elements"])


def test_screenshot_redaction_masks_password_fields():
    h, hwnd, proc = launch_pad("--protected")
    try:
        h.focus(hwnd)
        assert any("[password]" in line for line in h.screen(hwnd)["elements"])
        img = h.redacted_screenshot(hwnd)
        assert img.png.startswith(b"\x89PNG") and img.note.startswith(("1 regions", "2 regions"))
    finally:
        close_pad(h, hwnd, proc)
