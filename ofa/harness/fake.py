"""In-memory desktop for tests: windows, elements, apps, typing and clicks with observable effects."""
from __future__ import annotations

from .win import El


class FakeDesktop:
    def __init__(self):
        self.wins: dict[int, dict] = {}
        self.elements: dict[int, list[El]] = {}
        self.fg = 0
        self.apps = [{"name": "Notepad", "appid": "notepad"}, {"name": "Slack", "appid": "slack"},
                     {"name": "WhatsApp", "appid": "whatsapp"}, {"name": "Google Chrome", "appid": "chrome"},
                     {"name": "Settings", "appid": "settings"}]
        self.typed: list[tuple[int, str]] = []
        self.keys: list[str] = []
        self.clicks: list[str] = []
        self.opened: list[str] = []
        self.on_click = {}
        self.focused: El | None = None
        self._next = 100
        self.block_focus = False

    def add_window(self, title, process, elements=(), hwnd=None):
        hwnd = hwnd or self._next
        self._next += 1
        self.wins[hwnd] = {"hwnd": hwnd, "title": title, "pid": hwnd, "exe": f"C:/Apps/{process}",
                           "process": process, "class": "X", "rect": (0, 0, 800, 600), "minimized": False}
        self.elements[hwnd] = [El(f"u{i}", *e) if isinstance(e, tuple) else e for i, e in enumerate(elements)]
        self.fg = hwnd
        return hwnd

    # backend API --------------------------------------------------------------------------------
    def list_windows(self):
        return list(self.wins.values())

    def foreground(self):
        return self.fg

    def focus(self, hwnd):
        if self.block_focus:
            return False
        self.fg = hwnd
        return True

    def show(self, hwnd, how):
        self.wins[hwnd]["minimized"] = how == "minimize"

    def close_window(self, hwnd):
        if any(e.text == "Save changes?" for e in self.elements.get(hwnd, [])):
            return
        self.wins.pop(hwnd, None)

    def window_exists(self, hwnd):
        return hwnd in self.wins

    def move(self, hwnd, rect):
        self.wins[hwnd]["rect"] = rect

    def work_area(self):
        return (0, 0, 1920, 1080)

    def uia_tree(self, hwnd, **_):
        return [El(e.id, e.text, e.role, e.bbox, e.source, e.enabled, e.is_password, e.value, node=e)
                for e in self.elements.get(hwnd, [])], True

    def _real(self, el):
        return el.node if el.node is not None else el

    def uia_invoke(self, el):
        el = self._real(el)
        self.clicks.append(el.text)
        if el.text in self.on_click:
            self.on_click[el.text](self)
        return True

    def uia_set_value(self, el, text):
        self._real(el).value = text
        return True

    def uia_focus(self, el):
        self.focused = self._real(el)
        return True

    def uia_value(self, el):
        return self._real(el).value

    def focused_element(self):
        return self.focused

    def type_unicode(self, text):
        self.typed.append((self.fg, text))
        if self.focused is not None:
            self.focused.value = (self.focused.value or "") + text

    def press(self, combo):
        self.keys.append(combo)
        if combo == "ctrl+a" and self.focused is not None:
            self.focused.value = ""

    def click_at(self, x, y, button="left", double=False):
        self.clicks.append(f"@{x},{y}")

    def wheel(self, x, y, clicks):
        self.keys.append(f"wheel{clicks}")

    def drag(self, a, b):
        self.keys.append("drag")

    def capture(self, rect):
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        return b"\x10\x20\x30\xff" * (w * h), w, h

    def virtual_screen(self):
        return (0, 0, 1920, 1080)

    def ocr(self, bgra, w, h, origin=(0, 0)):
        return list(getattr(self, "ocr_lines", []))

    def to_png(self, bgra, w, h):
        return b"PNG" + bytes(bgra[:16])

    def installed_apps(self, refresh=False):
        return self.apps

    def launch(self, app):
        self.opened.append(app["name"])
        self.add_window(app["name"], app["appid"] + ".exe")

    def open_uri(self, uri):
        self.opened.append(uri)
