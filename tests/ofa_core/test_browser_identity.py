"""The page address the vault checks comes from the browser's own bar, never from the page."""
import pytest

from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.harness.win import El


def el(i, text, role, value=None):
    return El(f"u{i}", text, role, (0, 0, 5, 5), value=value)


@pytest.mark.parametrize("label", ["Email address", "Address", "Web address"])
@pytest.mark.parametrize("with_document", [True, False])
def test_a_page_field_cannot_pose_as_the_address_bar(label, with_document):
    desk = FakeDesktop()
    hwnd = desk.add_window("Sign in - Microsoft Edge", "msedge.exe", [])
    page = [el(2, "Sign in", "document")] if with_document else []
    desk.elements[hwnd] = [el(1, "Address and search bar", "edit", "https://evil.example/login"), *page,
                           el(3, label, "edit", "https://github.com/login")]
    assert Harness(desk).browser_identity(hwnd)["url"] == "https://evil.example/login"


def test_without_a_browser_address_bar_a_page_field_is_not_used():
    desk = FakeDesktop()
    hwnd = desk.add_window("Sign in - Microsoft Edge", "msedge.exe", [])
    desk.elements[hwnd] = [el(1, "Sign in", "document"), el(2, "Email address", "edit", "github.com")]
    assert Harness(desk).browser_identity(hwnd)["url"] is None


@pytest.mark.parametrize("order,url", [
    (["bar", "document", "spoof"], "https://evil.example/login"),     # the real bar comes first
    (["document", "spoof", "bar"], None),                             # cannot tell them apart
])
def test_a_field_copying_the_address_bar_name_is_not_trusted(order, url):
    parts = {"bar": el(1, "Address and search bar", "edit", "https://evil.example/login"),
             "document": el(2, "Sign in", "document"),
             "spoof": el(3, "Address and search bar", "edit", "https://github.com/login")}
    desk = FakeDesktop()
    hwnd = desk.add_window("Sign in - Microsoft Edge", "msedge.exe", [])
    desk.elements[hwnd] = [parts[name] for name in order]
    assert Harness(desk).browser_identity(hwnd)["url"] == url


def test_a_full_screen_page_with_no_address_bar_cannot_supply_one():
    """Seen in real Chrome full screen: the tree held the page and its fields, but no browser bar."""
    desk = FakeDesktop()
    hwnd = desk.add_window("Sign in - Google Chrome", "chrome.exe", [])
    desk.elements[hwnd] = [el(1, "Sign in", "document", "http://evil.example/login"),
                           el(2, "Address and search bar", "edit", "https://github.com/login")]
    identity = Harness(desk).browser_identity(hwnd)
    assert (identity["url"], identity["tls_ok"]) == (None, False)
