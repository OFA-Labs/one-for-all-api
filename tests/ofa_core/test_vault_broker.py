"""V1–V3, V5, V6, V8–V10: vault crypto, handles, broker identity checks, canaries."""
import sqlite3

import pytest

from ofa.egress import EGRESS, LeakBlocked
from ofa.vault import Vault, VaultLocked, parse_handle
from ofa.vault.broker import Broker, TargetIdentity
from ofa.vault.handles import HandleError


class Yes:
    def __init__(self, ok=True):
        self.ok, self.calls = ok, 0

    def verify(self, reason):
        self.calls += 1
        return self.ok


def fake_wrap(k):
    return bytes(b ^ 0x5A for b in k)


@pytest.fixture
def vault(tmp_path):
    v = Vault(tmp_path, Yes(), wrap=fake_wrap, unwrap=fake_wrap)
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


GH = TargetIdentity(kind="browser", url="https://github.com/login", tls_ok=True, field_is_password=True)


def test_handles_parse_and_reject():
    assert parse_handle("vault:D3/github/password#2").data_class == "D3"
    assert parse_handle("pm:bitwarden/abc-123/password").kind == "pm"
    assert parse_handle("session:gmail").kind == "session"
    for bad in ("vault:D9/x/y#1", "github password", "vault:D3/GitHub/pass word#1", ""):
        with pytest.raises(HandleError):
            parse_handle(bad)


def test_locked_vault_refuses(tmp_path):
    v = Vault(tmp_path, Yes(ok=False), wrap=fake_wrap, unwrap=fake_wrap)
    assert not v.unlock()
    with pytest.raises(VaultLocked):
        v.put("D3", "github", "password", "x")


def test_ciphertext_not_plaintext_and_tamper_detected(vault, tmp_path):
    h = vault.put("D3", "github", "password", "Correct-Horse-9", allowed_targets=["https://github.com"])
    raw = (tmp_path / "vault.db").read_bytes()
    assert b"Correct-Horse-9" not in raw
    db = sqlite3.connect(tmp_path / "vault.db")
    db.execute("UPDATE items SET handle='vault:D3/gitlab/password#1' WHERE handle=?", (h,))  # swap AAD
    db.commit()
    result = Broker(vault).fill("vault:D3/gitlab/password#1", "pw", GH, Field())
    assert not result.ok and result.reason in {"TAMPERED", "NO_ALLOWED_TARGETS"}


def test_fill_verified_origin_returns_no_value(vault):
    h = vault.put("D3", "github", "password", "Correct-Horse-9", allowed_targets=["https://github.com"])
    f = Field()
    result = Broker(vault).fill(h, "pw", GH, f)
    assert result.ok and f.values["pw"] == "Correct-Horse-9"
    assert "Correct-Horse-9" not in repr(result) and "Correct-Horse-9" not in str(Broker(vault).describe(h))


@pytest.mark.parametrize("url,reason", [
    ("https://evil.example/login", "WRONG_ORIGIN"),
    ("https://g1thub.com/login", "LOOKALIKE"),
    ("https://github.com.evil.io/login", "LOOKALIKE"),
    ("https://xn--gthub-n4a.com/", "LOOKALIKE"),
    ("http://github.com/login", "NOT_HTTPS"),
])
def test_wrong_and_lookalike_origins_refused(vault, url, reason):
    h = vault.put("D3", "github", "password", "Correct-Horse-9", allowed_targets=["https://github.com"])
    f = Field()
    result = Broker(vault).fill(h, "pw", TargetIdentity(kind="browser", url=url, tls_ok=True, field_is_password=True), f)
    assert not result.ok and result.reason == reason and not f.values


def test_tls_redirect_and_frame_checks(vault):
    h = vault.put("D3", "github", "password", "pw-123456", allowed_targets=["https://github.com"])
    b = Broker(vault)
    assert b.fill(h, "p", TargetIdentity("browser", GH.url, tls_ok=False, field_is_password=True), Field()).reason == "TLS_ERROR"
    assert b.fill(h, "p", TargetIdentity("browser", GH.url, True, redirected=True, field_is_password=True), Field()).reason == "REDIRECTED"
    assert b.fill(h, "p", TargetIdentity("browser", GH.url, True, frame_origin="https://ads.net", field_is_password=True),
                  Field()).reason == "CROSS_ORIGIN_FRAME"
    assert b.fill(h, "p", TargetIdentity("browser", GH.url, True, field_is_password=False), Field()).reason == "NOT_A_PASSWORD_FIELD"


def test_app_identity(vault):
    h = vault.put("D3", "slack", "password", "pw-123456", allowed_targets=["app:C:/Apps/slack.exe|Slack Technologies"])
    b = Broker(vault)
    ok = TargetIdentity("app", exe_path="C:\\Apps\\slack.exe", publisher="Slack Technologies")
    bad = TargetIdentity("app", exe_path="C:\\Temp\\slack.exe", publisher="Slack Technologies")
    assert b.fill(h, "f", ok, Field()).ok
    assert b.fill(h, "f", bad, Field()).reason == "APP_MISMATCH"


def test_revoke_rotate_delete(vault):
    h1 = vault.put("D3", "github", "password", "old-pass-1", allowed_targets=["https://github.com"])
    h2 = vault.rotate(h1, "new-pass-2")
    assert h2.endswith("#2") and vault.meta(h1)["revoked"]
    assert Broker(vault).fill(h1, "p", GH, Field()).reason == "REVOKED"
    vault.revoke(h2)
    assert Broker(vault).fill(h2, "p", GH, Field()).reason == "REVOKED"
    vault.delete(h2)
    assert Broker(vault).fill(h2, "p", GH, Field()).reason == "UNKNOWN_HANDLE"


def test_d2_requires_approval_each_time(vault):
    h = vault.put("D2", "gov", "pan", "ABCDE1234F", allowed_targets=["https://portal.example.gov"])
    ident = TargetIdentity("browser", "https://portal.example.gov/form", True)
    assert Broker(vault).fill(h, "f", ident, Field()).reason == "APPROVAL_REQUIRED"
    assert Broker(vault).fill(h, "f", ident, Field(), approved=True).ok


def test_released_secret_never_leaves_via_egress(vault):
    h = vault.put("D3", "github", "password", "Correct-Horse-9", allowed_targets=["https://github.com"])
    Broker(vault).fill(h, "pw", GH, Field())
    for sink_payload in ({"messages": [{"role": "tool", "content": "page shows Correct-Horse-9"}]},
                         "transcript: correct-horse-9", "Q29ycmVjdC1Ib3JzZS05"):
        with pytest.raises(LeakBlocked):
            EGRESS.guard(sink_payload, "llm")


def test_unlock_arms_canaries_for_existing_secrets(tmp_path):
    v = Vault(tmp_path, Yes(), wrap=fake_wrap, unwrap=fake_wrap)
    v.unlock()
    v.put("D3", "x", "token", "tok-abcdef-777", allowed_targets=["https://x.com"])
    EGRESS.forget_all()
    v.lock()
    v2 = Vault(tmp_path, Yes(), wrap=fake_wrap, unwrap=fake_wrap)
    v2.unlock()
    with pytest.raises(LeakBlocked):
        EGRESS.guard("tok-abcdef-777", "log")
    EGRESS.forget_all()
