"""Credential broker (§8.4). Verifies the real target identity against the handle allowlist, injects
through the most direct channel, zeroizes, and returns success/failure only — never a value."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

from rapidfuzz import fuzz

from ..egress import EGRESS
from .handles import HandleError, parse_handle
from .store import Vault, VaultError, VaultLocked

CONFUSABLE = str.maketrans({"0": "o", "1": "l", "3": "e", "5": "s", "7": "t", "@": "a", "$": "s", "|": "l",
                            "і": "i", "о": "o", "а": "a", "е": "e", "р": "p", "с": "c", "у": "y", "х": "x",
                            "ԁ": "d", "ɡ": "g", "ⅼ": "l", "ı": "i", "ս": "u"})


@dataclass
class TargetIdentity:
    kind: str                      # browser | app
    url: str | None = None         # top-frame URL as read from the browser itself
    tls_ok: bool = False           # no certificate error reported by the browser
    frame_origin: str | None = None
    redirected: bool = False       # top URL changed since the step was observed
    exe_path: str | None = None
    publisher: str | None = None
    field_is_password: bool = False


class Injector(Protocol):
    def set_value(self, field_ref: str, value: str) -> bool: ...
    def field_length(self, field_ref: str) -> int: ...


@dataclass
class FillResult:
    ok: bool
    reason: str = "ok"


def origin_of(url: str | None) -> str | None:
    if not url:
        return None
    p = urlsplit(url)
    if not p.scheme or not p.hostname:
        return None
    host = p.hostname.encode("idna").decode() if any(ord(c) > 127 for c in p.hostname) else p.hostname
    port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
    return f"{p.scheme}://{host.lower()}{port}"


def _skeleton(host: str) -> str:
    try:
        host = host.encode().decode("idna") if "xn--" in host else host
    except UnicodeError:
        pass
    host = unicodedata.normalize("NFKC", host).lower().translate(CONFUSABLE)
    return host.replace("rn", "m").replace("vv", "w")


def check_origin(identity: TargetIdentity, allowed: list[str]) -> str:
    origin = origin_of(identity.url)
    if not origin:
        return "NO_ORIGIN"
    if identity.redirected:
        return "REDIRECTED"
    if not origin.startswith("https://") and not origin.startswith("http://127.0.0.1"):
        return "NOT_HTTPS"
    if origin.startswith("https://") and not identity.tls_ok:
        return "TLS_ERROR"
    if identity.frame_origin and origin_of(identity.frame_origin) != origin:
        return "CROSS_ORIGIN_FRAME"
    host = urlsplit(origin).hostname or ""
    for rule in allowed:
        if rule == origin:
            return "ok"
        if rule.startswith("https://*.") and origin.startswith("https://"):
            suffix = rule[len("https://*."):]
            if host == suffix or host.endswith("." + suffix):
                return "ok"
    for rule in allowed:
        rhost = urlsplit(rule.replace("*.", "")).hostname or ""
        if "xn--" in host or _skeleton(host) == _skeleton(rhost) or fuzz.ratio(host, rhost) >= 80 or rhost in host:
            return "LOOKALIKE"
    return "WRONG_ORIGIN"


def check_app(identity: TargetIdentity, allowed: list[str]) -> str:
    exe = (identity.exe_path or "").replace("\\", "/").lower()
    for rule in allowed:
        if not rule.startswith("app:"):
            continue
        spec = rule[4:]
        path, _, publisher = spec.partition("|")
        if exe and exe == path.replace("\\", "/").lower() and (not publisher or publisher == identity.publisher):
            return "ok"
    return "APP_MISMATCH"


class PasswordManager(Protocol):
    def get(self, item: str, field: str) -> str: ...


class Broker:
    def __init__(self, vault: Vault, managers: dict[str, PasswordManager] | None = None, audit=None):
        self.vault, self.managers, self.audit = vault, managers or {}, audit

    def describe(self, handle: str) -> dict:
        """Non-secret metadata for the engine."""
        h = parse_handle(handle)
        if h.kind == "vault":
            m = self.vault.meta(handle)
            return {k: m[k] for k in ("handle", "class", "service", "label", "allowed_targets", "ops", "revoked")}
        return {"handle": handle, "class": h.data_class, "service": h.service, "label": h.label}

    def _value(self, handle: str) -> tuple[str, list[str]]:
        h = parse_handle(handle)
        if h.kind == "vault":
            meta = self.vault.meta(handle)
            if meta["revoked"]:
                raise VaultError("REVOKED")
            return self.vault.reveal_for_broker(handle), meta["allowed_targets"]
        if h.kind == "pm":
            manager = self.managers.get(h.service)
            if manager is None:
                raise VaultError("PM_NOT_LINKED")
            item, field = h.label.split("/", 1)
            targets = getattr(manager, "targets", lambda _i: [])(item)
            value = manager.get(item, field)
            EGRESS.register(value, handle)
            return value, targets
        raise VaultError("SESSION_HANDLE_HAS_NO_VALUE")

    def fill(self, handle: str, field_ref: str, identity: TargetIdentity, injector: Injector,
             approved: bool = False) -> FillResult:
        try:
            h = parse_handle(handle)
        except HandleError:
            return self._done(handle, FillResult(False, "BAD_HANDLE"))
        if (h.data_class == "D2" or "totp" in h.label) and not approved:
            return self._done(handle, FillResult(False, "APPROVAL_REQUIRED"))
        try:
            value, allowed = self._value(handle)
        except VaultLocked:
            return self._done(handle, FillResult(False, "LOCKED"))
        except VaultError as exc:
            return self._done(handle, FillResult(False, exc.code))
        except Exception:
            return self._done(handle, FillResult(False, "PM_UNAVAILABLE"))
        try:
            if not allowed:
                return self._done(handle, FillResult(False, "NO_ALLOWED_TARGETS"))
            verdict = check_origin(identity, allowed) if identity.kind == "browser" else check_app(identity, allowed)
            if verdict != "ok":
                return self._done(handle, FillResult(False, verdict))
            if h.data_class == "D3" and h.label.endswith("password") and identity.kind == "browser" \
                    and not identity.field_is_password:
                return self._done(handle, FillResult(False, "NOT_A_PASSWORD_FIELD"))
            if not injector.set_value(field_ref, value):
                return self._done(handle, FillResult(False, "INJECT_FAILED"))
            ok = injector.field_length(field_ref) >= len(value) or identity.field_is_password
            return self._done(handle, FillResult(ok, "ok" if ok else "NOT_VERIFIED"))
        finally:
            value = "\0" * len(value)
            del value

    def _done(self, handle: str, result: FillResult) -> FillResult:
        if self.audit:
            self.audit.write("broker_fill", handle_ids=[handle], result=result.reason)
        return result
