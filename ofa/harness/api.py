"""Desktop harness (§10.1): one small helper API; backends accessibility → OCR → vision.
Results returned to the engine are untrusted data. Every call arrives via ofa.executor."""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from rapidfuzz import fuzz, process

from ..engine.base import RedactedImage

BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "vivaldi.exe", "arc.exe"}
ADDRESS_NAMES = ("address and search bar", "address bar", "search or enter address", "search with google or enter address")
_REDACT_TOKEN = object()


class HarnessError(RuntimeError):
    def __init__(self, code: str, message: str = "", options: list | None = None):
        super().__init__(message or code)
        self.code, self.options = code, options or []


@dataclass
class Snapshot:
    hwnd: int
    title: str
    process: str
    elements: list
    complete: bool
    sources: tuple[str, ...]
    at: float

    def by_id(self, eid: str):
        for e in self.elements:
            if e.id == eid:
                return e
        raise HarnessError("STALE_ELEMENT", f"No element {eid} on the last reading; read the screen again")


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").casefold()).strip()


class Harness:
    def __init__(self, backend=None):
        if backend is None:
            from . import win as backend
        self.b = backend
        self.last: Snapshot | None = None
        self.filled_refs: set[tuple[int, str]] = set()     # broker-filled fields to redact
        self.vision_ok = False

    # --- windows ---------------------------------------------------------------------------
    def windows(self) -> list[dict]:
        return [{"title": w["title"][:100], "app": w["process"].removesuffix(".exe"), "hwnd": w["hwnd"],
                 "minimized": w["minimized"]} for w in self.b.list_windows()]

    def resolve_window(self, query: str | int | None) -> dict:
        wins = self.b.list_windows()
        if query in (None, "", "current", "foreground"):
            fg = self.b.foreground()
            for w in wins:
                if w["hwnd"] == fg:
                    return w
            if wins:
                return wins[0]
            raise HarnessError("NO_WINDOW", "No window is open")
        if isinstance(query, int) or str(query).isdigit():
            for w in wins:
                if w["hwnd"] == int(query):
                    return w
            raise HarnessError("WINDOW_GONE", "That window is no longer open")
        q = norm(str(query)).removesuffix(".exe")
        scored = []
        for w in wins:
            proc = w["process"].removesuffix(".exe")
            s = max(fuzz.partial_ratio(q, norm(w["title"])) if len(q) >= 3 else 0,
                    100 if q == proc else fuzz.ratio(q, proc))
            if s >= 75:
                scored.append((s, w))
        if not scored:
            raise HarnessError("WINDOW_NOT_FOUND", f"No open window matches {query}")
        scored.sort(key=lambda x: -x[0])
        top = [w for s, w in scored if s == scored[0][0]]
        if len(top) > 1 and len({w["process"] for w in top}) > 1:
            raise HarnessError("AMBIGUOUS", "Several windows match",
                               [{"title": w["title"][:80], "hwnd": w["hwnd"]} for w in top[:5]])
        return top[0]

    def focus(self, window) -> dict:
        w = self.resolve_window(window)
        ok = self.b.focus(w["hwnd"])
        if not ok and self.b.foreground() != w["hwnd"]:
            raise HarnessError("FOCUS_FAILED", "Windows would not bring that window to the front")
        return {"focused": w["title"][:100], "hwnd": w["hwnd"], "verified": True}

    def window_op(self, window, op: str) -> dict:
        w = self.resolve_window(window)
        if op == "close":
            self.b.close_window(w["hwnd"])
            for _ in range(30):
                time.sleep(0.1)
                if not self.b.window_exists(w["hwnd"]):
                    return {"closed": w["title"][:100], "verified": True}
            fg = self.b.foreground()
            return {"closed": False, "verified": False, "reason": "The window is still open; it may be asking to save",
                    "dialog": next((x["title"] for x in self.b.list_windows() if x["hwnd"] == fg), "")}
        if op in {"minimize", "maximize", "restore"}:
            self.b.show(w["hwnd"], op)
            time.sleep(0.2)
            return {op: w["title"][:100], "verified": True}
        if op in {"left", "right", "top", "bottom", "full"}:
            l, t, r, b = self.b.work_area()
            mid_x, mid_y = (l + r) // 2, (t + b) // 2
            rect = {"left": (l, t, mid_x, b), "right": (mid_x, t, r, b), "top": (l, t, r, mid_y),
                    "bottom": (l, mid_y, r, b), "full": (l, t, r, b)}[op]
            self.b.move(w["hwnd"], rect)
            return {"arranged": op, "window": w["title"][:100], "verified": True}
        raise HarnessError("BAD_OP", op)

    # --- opening ---------------------------------------------------------------------------
    def find_app(self, name: str) -> dict:
        apps = self.b.installed_apps()
        if not apps:
            raise HarnessError("DISCOVERY_FAILED", "Could not list installed apps")
        q = norm(name)
        names = [norm(a["name"]) for a in apps]
        exact = [a for a, n in zip(apps, names) if n == q]
        if len(exact) >= 1:
            pick = [a for a in exact if a.get("appid")] or exact
            return pick[0]
        matches = process.extract(q, names, scorer=fuzz.WRatio, limit=5)
        good = [(apps[i], s) for _, s, i in matches if s >= 86]
        if not good:
            raise HarnessError("NOT_INSTALLED", f"I couldn't find an installed app called {name}",
                               [apps[i]["name"] for _, s, i in matches if s >= 60][:3])
        best = good[0][1]
        top = [a for a, s in good if s >= best - 2]
        uniq = {norm(a["name"]) for a in top}
        if len(uniq) > 1 and best < 95:
            raise HarnessError("AMBIGUOUS", "Several apps match", [a["name"] for a in top][:5])
        return top[0]

    def open_app(self, name: str, timeout: float = 20.0) -> dict:
        try:
            w = self.resolve_window(name)
            self.b.focus(w["hwnd"])
            return {"opened": w["title"][:100], "already_running": True, "hwnd": w["hwnd"], "verified": True}
        except HarnessError as e:
            if e.code == "AMBIGUOUS":
                raise
        app = self.find_app(name)
        before = {w["hwnd"] for w in self.b.list_windows()}
        self.b.launch(app)
        key = norm(app["name"]).split(" ")[0]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.4)
            for w in self.b.list_windows():
                new = w["hwnd"] not in before
                if new or key in norm(w["title"]) or key in w["process"]:
                    if new or self.b.foreground() == w["hwnd"]:
                        return {"opened": app["name"], "window": w["title"][:100], "hwnd": w["hwnd"], "verified": True}
        raise HarnessError("LAUNCH_NOT_VERIFIED", f"{app['name']} was started but no window appeared in time")

    def open_url(self, url: str, timeout: float = 15.0) -> dict:
        p = urlsplit(url)
        if p.scheme not in {"http", "https"} or not p.hostname or p.username or p.password:
            raise HarnessError("URL_DENIED", "Only plain http(s) addresses can be opened")
        self.b.open_uri(url)
        host = p.hostname.lower().removeprefix("www.")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(0.5)
            ident = self.browser_identity()
            if ident and ident.get("url") and host in (urlsplit(ident["url"]).hostname or "").lower():
                return {"opened": url, "verified_url": ident["url"], "verified": True}
        return {"opened": url, "verified": False, "reason": "Sent to the browser but the address bar could not be confirmed"}

    def open_path(self, path: str) -> dict:
        if path.startswith("ms-settings:"):
            self.b.open_uri(path)
            time.sleep(1.2)
            w = self.resolve_window("settings")
            return {"opened": path, "window": w["title"], "verified": True}
        if not os.path.exists(path):
            raise HarnessError("PATH_NOT_FOUND", "That file or folder does not exist")
        self.b.open_uri(path)
        time.sleep(1.0)
        base = os.path.basename(path.rstrip("\\/")).casefold()
        stem = os.path.splitext(base)[0]
        for w in self.b.list_windows():
            if stem and stem in w["title"].casefold():
                return {"opened": path, "window": w["title"][:100], "verified": True}
        return {"opened": path, "verified": False, "reason": "No window titled with that name appeared"}

    # --- reading ---------------------------------------------------------------------------
    def screen(self, window=None, ocr: bool | None = None, limit: int = 80) -> dict:
        w = self.resolve_window(window)
        els, complete = self.b.uia_tree(w["hwnd"])
        sources = ["uia"]
        texty = [e for e in els if e.text or e.value]
        if ocr or (ocr is None and len(texty) < 8):
            try:
                bgra, width, height = self.b.capture(w["rect"])
                extra = self.b.ocr(bgra, width, height, (w["rect"][0], w["rect"][1]))
                known = {norm(e.text) for e in els}
                start = len(els)
                for i, e in enumerate(x for x in extra if norm(x.text) not in known):
                    e.id = f"o{start + i}"
                    els.append(e)
                sources.append("ocr")
            except Exception:
                pass
        for e in els:
            if (w["hwnd"], e.id) in self.filled_refs or e.is_password:
                e.value = None
        self.last = Snapshot(w["hwnd"], w["title"], w["process"], els, complete, tuple(sources), time.monotonic())
        shown = self._rank(els)[:limit]
        return {"window": w["title"][:100], "app": w["process"].removesuffix(".exe"), "complete": complete,
                "sources": sources, "count": len(els), "elements": [e.public() for e in shown],
                "truncated": len(els) > len(shown)}

    @staticmethod
    def _rank(els):
        prio = {"edit": 0, "button": 1, "hyperlink": 1, "link": 1, "list item": 2, "menu item": 2, "tab item": 2,
                "check box": 2, "combo box": 1, "document": 0, "tree item": 2}
        return sorted(els, key=lambda e: (prio.get(e.role, 3), e.bbox[1], e.bbox[0]))

    def find_text(self, query: str, role: str | None = None, window=None) -> dict:
        if self.last is None or (window and self.resolve_window(window)["hwnd"] != self.last.hwnd):
            self.screen(window)
        q = norm(query)
        cands = [e for e in self.last.elements if not role or e.role == role.lower()]
        exact = [e for e in cands if norm(e.text) == q or norm(e.value or "") == q]
        if exact:
            return {"match": "exact", "elements": [e.public() for e in exact[:5]]}
        contains = [e for e in cands if q and q in norm(e.text)]
        if contains:
            return {"match": "contains", "elements": [e.public() for e in contains[:5]]}
        fuzzy = sorted(((fuzz.WRatio(q, norm(e.text)), e) for e in cands if e.text), key=lambda x: -x[0])
        near = [e.public() for s, e in fuzzy[:3] if s >= 85]
        return {"match": "fuzzy" if near else "none", "elements": near,
                "note": "fuzzy matches are NOT confirmed matches" if near else "not on screen"}

    def wait_for_text(self, query: str, window=None, timeout: float = 10.0) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.screen(window)
            r = self.find_text(query)
            if r["match"] in {"exact", "contains"}:
                return {"found": True, **r}
            time.sleep(0.6)
        return {"found": False}

    def element(self, ref: str):
        if self.last is None:
            raise HarnessError("NO_READING", "Read the screen first")
        if ref.startswith(("u", "o")) and ref[1:].isdigit():
            return self.last.by_id(ref)
        r = self.find_text(ref)
        if r["match"] in {"exact", "contains"} and len(r["elements"]) >= 1:
            return self.last.by_id(r["elements"][0]["id"])
        raise HarnessError("ELEMENT_NOT_FOUND", f"No element matching {ref!r}")

    # --- acting ----------------------------------------------------------------------------
    def _ensure_front(self) -> None:
        if self.last and self.b.foreground() != self.last.hwnd:
            if not self.b.focus(self.last.hwnd):
                raise HarnessError("FOCUS_FAILED", "The target window is not in front; nothing was typed")

    def click(self, ref: str, double: bool = False, button: str = "left") -> dict:
        el = self.element(ref)
        if not el.enabled:
            raise HarnessError("DISABLED", f"{el.text or el.role} is disabled")
        before = self._fingerprint()
        self._ensure_front()
        used = "uia"
        if double or button != "left" or el.source != "uia" or not self.b.uia_invoke(el):
            self.b.click_at(*el.center(), button=button, double=double)
            used = "mouse"
        time.sleep(0.35)
        changed = self._fingerprint() != before
        return {"clicked": el.text or el.role, "method": used, "screen_changed": changed, "verified": changed}

    def type_text(self, text: str, ref: str | None = None, replace: bool = False) -> dict:
        el = self.element(ref) if ref else None
        self._ensure_front()
        if el is not None:
            if el.is_password:
                raise HarnessError("PROTECTED_FIELD", "Passwords are filled only by the credential broker")
            if replace and self.b.uia_set_value(el, text):
                return {"typed": len(text), "method": "set_value", "readback": self.readback(ref)}
            if el.source == "uia" and not self.b.uia_focus(el):
                self.b.click_at(*el.center())
            elif el.source != "uia":
                self.b.click_at(*el.center())
            if replace:
                self.b.press("ctrl+a")
        self.b.type_unicode(text)
        return {"typed": len(text), "method": "keyboard", "readback": self.readback(ref) if ref else None}

    def readback(self, ref: str | None) -> str | None:
        el = self.element(ref) if ref else self.b.focused_element()
        if el is None or el.is_password:
            return None
        return self.b.uia_value(el)

    def key(self, combo: str) -> dict:
        before = self._fingerprint()
        self._ensure_front()
        self.b.press(combo)
        time.sleep(0.3)
        changed = self._fingerprint() != before
        return {"pressed": combo, "screen_changed": changed, "verified": changed}

    def scroll(self, direction: str = "down", amount: int = 5, ref: str | None = None) -> dict:
        before = self._fingerprint()
        if ref:
            x, y = self.element(ref).center()
        elif self.last:
            w = next((w for w in self.b.list_windows() if w["hwnd"] == self.last.hwnd), None)
            if w is None:
                raise HarnessError("WINDOW_GONE")
            x, y = (w["rect"][0] + w["rect"][2]) // 2, (w["rect"][1] + w["rect"][3]) // 2
        else:
            raise HarnessError("NO_READING", "Read the screen first")
        self._ensure_front()
        self.b.wheel(x, y, -amount if direction == "down" else amount)
        time.sleep(0.3)
        changed = self._fingerprint() != before
        return {"scrolled": direction, "screen_changed": changed, "verified": changed,
                "note": None if changed else "nothing moved: end of content or not scrollable"}

    def drag(self, src: str, dst: str) -> dict:
        a, b = self.element(src).center(), self.element(dst).center()
        self._ensure_front()
        self.b.drag(a, b)
        return {"dragged": True}

    def _fingerprint(self) -> str:
        if not self.last:
            return ""
        try:
            els, _ = self.b.uia_tree(self.last.hwnd, max_nodes=600, budget_s=0.8)
            return "|".join(f"{e.role}:{e.text}:{e.value}" for e in els[:300])
        except Exception:
            return ""

    # --- identity & images -------------------------------------------------------------------
    def browser_identity(self, window=None) -> dict | None:
        try:
            w = self.resolve_window(window)
        except HarnessError:
            return None
        if w["process"] not in BROWSERS:
            wins = [x for x in self.b.list_windows() if x["process"] in BROWSERS]
            if not wins:
                return None
            w = wins[0]
        els, _ = self.b.uia_tree(w["hwnd"], max_nodes=900, budget_s=1.2)
        url, insecure = None, False
        for e in els:
            name = norm(e.text)
            if e.role in {"edit", "combo box"} and (name in ADDRESS_NAMES or "address" in name) and e.value:
                url = e.value.strip()
            if name in {"not secure", "your connection is not private", "dangerous"}:
                insecure = True
        if url and "://" not in url:
            url = "https://" + url
        return {"url": url, "tls_ok": bool(url) and url.startswith("https://") and not insecure,
                "browser": w["process"], "hwnd": w["hwnd"]}

    def redacted_screenshot(self, window=None, extra_regions: list | None = None) -> RedactedImage:
        w = self.resolve_window(window)
        bgra, width, height = self.b.capture(w["rect"])
        buf = bytearray(bgra)
        els, _ = self.b.uia_tree(w["hwnd"])
        boxes = [e.bbox for e in els if e.is_password or (w["hwnd"], e.id) in self.filled_refs]
        boxes += list(extra_regions or [])
        ox, oy = w["rect"][0], w["rect"][1]
        for l, t, r, b in boxes:
            for y in range(max(0, t - oy), min(height, b - oy)):
                row = y * width * 4
                x0, x1 = max(0, l - ox), min(width, r - ox)
                if x1 > x0:
                    buf[row + x0 * 4: row + x1 * 4] = b"\x00\x00\x00\xff" * (x1 - x0)
        return RedactedImage(self.b.to_png(bytes(buf), width, height), f"{len(boxes)} regions masked", _REDACT_TOKEN)
