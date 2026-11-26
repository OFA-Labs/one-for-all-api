"""Credential fill: builds the real target identity and hands it to the broker."""
from __future__ import annotations

from ..harness.api import BROWSERS, Harness
from ..policy import Action
from ..vault.broker import Broker, TargetIdentity


def fill_secret(h: Harness, broker: Broker | None, a: Action) -> dict:
    if broker is None:
        return {"status": "error", "reason": "VAULT_UNAVAILABLE"}
    el = h.element(a.args.get("element") or "")
    proc = h.last.process if h.last else ""
    if proc in BROWSERS:
        ident = h.browser_identity(h.last.hwnd) or {}
        identity = TargetIdentity("browser", url=ident.get("url"), tls_ok=ident.get("tls_ok", False),
                                  field_is_password=el.is_password)
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
