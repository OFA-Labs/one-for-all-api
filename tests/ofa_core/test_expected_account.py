"""A saved secret is only typed for the account it was saved for."""
import pytest

from ofa.egress import EGRESS
from ofa.effects.credentials import fill_secret, shown_account
from ofa.harness.win import El
from ofa.policy import Action
from ofa.vault import Vault
from ofa.vault.broker import Broker, TargetIdentity


class Yes:
    def verify(self, reason):
        return True


def flip(key):
    return bytes(b ^ 0x5A for b in key)


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path, Yes(), wrap=flip, unwrap=flip)
    assert v.unlock()
    yield v
    EGRESS.forget_all()


class Field:
    def __init__(self):
        self.values = {}

    def set_value(self, ref, value):
        self.values[ref] = value
        return True

    def field_length(self, ref):
        return len(self.values.get(ref, ""))


def save(vault, **extra):
    return vault.put("D3", "github", "password", "Correct-Horse-9", allowed_targets=["https://github.com"], **extra)


def page(account):
    return TargetIdentity("browser", "https://github.com/login", True, field_is_password=True, account=account)


def test_the_expected_account_is_filled(vault):
    handle = save(vault, expected_account="Asha@Example.test")
    field = Field()
    assert Broker(vault).fill(handle, "pw", page("asha@example.test "), field).ok and field.values


@pytest.mark.parametrize("shown", ["ravi@example.test", "asha@example.test.evil", "", None])
def test_another_or_unreadable_account_is_refused(vault, shown):
    handle = save(vault, expected_account="asha@example.test")
    field = Field()
    result = Broker(vault).fill(handle, "pw", page(shown), field)
    assert (result.ok, result.reason, field.values) == (False, "ACCOUNT_MISMATCH", {})


def test_items_without_an_expected_account_behave_as_before(vault):
    assert Broker(vault).fill(save(vault), "pw", page(None), Field()).ok


def test_the_origin_is_checked_first(vault):
    handle = save(vault, expected_account="asha@example.test")
    wrong = TargetIdentity("browser", "https://evil.example/", True, field_is_password=True, account="asha@example.test")
    assert Broker(vault).fill(handle, "pw", wrong, Field()).reason == "WRONG_ORIGIN"


def test_rotating_or_retargeting_keeps_the_expected_account(vault):
    handle = vault.rotate(save(vault, expected_account="asha@example.test"), "New-Horse-10")
    vault.set_targets(handle, ["https://github.com"])
    assert vault.meta(handle)["expected_account"] == "asha@example.test"
    assert "expected_account" not in Broker(vault).describe(handle)       # not shown to the model


def el(i, text, role, value=None, password=False):
    return El(f"u{i}", text, role, (0, 0, 5, 5), value=value, is_password=password)


@pytest.mark.parametrize("elements,account", [
    ([el(1, "Username or email address", "edit", "Asha@example.test")], "asha@example.test"),
    ([el(1, "Signed in as asha-rao.", "text")], "asha-rao"),
    ([el(1, "Email", "edit", "a@x.test"), el(2, "Signed in as b@x.test", "text")], None),   # ambiguous
    ([el(1, "Share with asha@example.test", "text")], None),                                # just page text
    ([el(1, "Address and search bar", "edit", "asha@example.test")], None),
    ([el(1, "Account password", "edit", "asha@example.test", password=True)], None),
    ([el(1, "Email", "edit", "")], None),
])
def test_only_account_fields_and_signed_in_lines_count(elements, account):
    assert shown_account(elements) == account


def test_the_effect_reads_the_account_from_the_page(vault, tmp_path):
    from ofa.harness.api import Harness
    from ofa.harness.fake import FakeDesktop

    handle = save(vault, expected_account="asha@example.test")
    for typed, ok in (("ravi@example.test", False), ("asha@example.test", True)):
        desk = FakeDesktop()
        hwnd = desk.add_window("Sign in - Microsoft Edge", "msedge.exe", [])
        secret = el(3, "Password", "edit", password=True)
        desk.elements[hwnd] = [el(1, "Address and search bar", "edit", "https://github.com/login"),
                               el(2, "Username or email address", "edit", typed), secret]
        harness = Harness(desk)
        harness.screen(hwnd)
        action = Action(verb="fill_secret", handle=handle, args={"element": "u3"})
        assert fill_secret(harness, Broker(vault), action)["filled"] is ok
        assert bool(secret.value) is ok
