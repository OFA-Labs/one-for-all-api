"""Credential fill: builds the real target identity and hands it to the broker."""
from __future__ import annotations

import re

from ..harness.api import BROWSERS, Harness
from ..policy import Action
from ..vault.broker import Broker, TargetIdentity


ACCOUNT_FIELD = re.compile(r"\b(e-?mail( address)?|user ?name|user id|login id|account)\b", re.I)
SIGNED_IN = re.compile(r"\b(?:signed|logged) in as:?\s+([^\s,;()]+)", re.I)


def shown_account(elements) -> str | None:
    """The account this reading is about: an account field's value or a "signed in as" line.

    Anything else on the page is ignored. Two different answers mean the page is ambiguous, so none is given.
    """
    found = set()
    for e in elements:
        if e.role in {"edit", "combo box"} and not e.is_password and e.value and ACCOUNT_FIELD.search(e.text or ""):
            found.add(e.value.strip().casefold())
        line = SIGNED_IN.search(e.text or "")
        if line:
            found.add(line.group(1).rstrip(".").casefold())
    return found.pop() if len(found) == 1 else None


def fill_secret(h: Harness, broker: Broker | None, a: Action) -> dict:
    if broker is None:
        return {"status": "error", "reason": "VAULT_UNAVAILABLE"}
    el = h.element(a.args.get("element") or "")
    proc = h.last.process if h.last else ""
    if proc in BROWSERS:
        ident = h.browser_identity(h.last.hwnd) or {}
        identity = TargetIdentity("browser", url=ident.get("url"), tls_ok=ident.get("tls_ok", False),
                                  field_is_password=el.is_password,
                                  account=shown_account(h.last.elements))
    else:
        w = next((w for w in h.b.list_windows() if h.last and w["hwnd"] == h.last.hwnd), {})
        identity = TargetIdentity("app", exe_path=w.get("exe"), publisher=None, field_is_password=el.is_password)

    class Inject:
        def set_value(self, ref, value):
            if h.b.uia_set_value(el, value):
                return True
            h._ensure_front()
            h.b.uia_focus(el) or h.b.click_at(*el.center())
            h.b.press("ctrl+a")
            h.b.type_unicode(value)
            return True

        def field_length(self, ref):
            v = h.b.uia_value(el)
            return len(v or "")
    res = broker.fill(a.handle or "", el.id, identity, Inject(), approved=True)
    if res.ok and h.last:
        h.filled_refs.add((h.last.hwnd, el.id))
    return {"filled": res.ok, "reason": res.reason, "verified": res.ok}
