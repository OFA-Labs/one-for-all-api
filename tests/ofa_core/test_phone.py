"""Ph1–Ph3: phone surface works over a fake adb; phone sends are Tier 2; no network/cloud path exists."""
import ast
from pathlib import Path

import pytest

from ofa.phone import Phone, PhoneError
from ofa.policy import Action, classify_tier

XML = """<?xml version='1.0'?><hierarchy><node text="Chats" class="android.widget.TextView" bounds="[0,0][200,80]"/>
<node text="" content-desc="Send" class="android.widget.ImageButton" bounds="[900,1800][1000,1900]"/>
<node text="hunter" class="android.widget.EditText" password="true" bounds="[0,300][800,380]"/></hierarchy>"""


class FakeAdb:
    def __init__(self, locked=False):
        self.calls, self.locked = [], locked

    def __call__(self, args, timeout=15):
        self.calls.append(args)
        if args == ["devices"]:
            return "List of devices attached\nABC123\tdevice\n"
        if "dumpsys" in args:
            return "mShowingLockscreen=true" if self.locked else "mShowingLockscreen=false"
        if "cat" in args:
            return XML
        if "content" in args:
            return "Row: 0 address=VK-HDFCBK, body=Your OTP is 482913 for login\n"
        return ""


def test_screen_tap_and_password_flag():
    adb = FakeAdb()
    p = Phone(adb)
    s = p.screen()
    assert s["count"] == 3 and any("[password]" in e for e in s["elements"])
    p.tap("Send")
    assert ["-s", "ABC123", "shell", "input", "tap", "950", "1850"] in adb.calls


def test_locked_phone_is_a_handoff():
    with pytest.raises(PhoneError) as e:
        Phone(FakeAdb(locked=True)).screen()
    assert e.value.code == "LOCKED"


def test_sms_code_and_phone_send_tier():
    assert Phone(FakeAdb()).latest_sms_code("HDFC") == "482913"
    assert classify_tier(Action(verb="phone_send", payload="hi")) == 2
    assert classify_tier(Action(verb="release_otp")) == 2


def test_no_network_or_cloud_code_in_phone_surface():
    tree = ast.parse(Path("ofa/phone.py").read_text(encoding="utf-8"))
    names = {n.names[0].name for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and n.names} | \
            {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"httpx", "requests", "urllib.request", "socket", "phone_harness"}
