"""Windows primitives: windows, processes, UIA tree, input (SendInput), capture (mss), OCR (WinRT).
No elevation. Every call here is reached only through the hands graph (policy first)."""
from __future__ import annotations

import ctypes
import os
import subprocess
import threading
import time
from ctypes import wintypes as wt
from dataclasses import dataclass, field

from ofa_execution.windows import IS_WINDOWS, Input, KeyInput, MouseInput, process_identity
from ofa_execution.windows import windows as _windows

if IS_WINDOWS:
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.GetForegroundWindow.restype = wt.HWND
    user.SetForegroundWindow.argtypes = [wt.HWND]
    user.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    user.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    user.IsIconic.argtypes = [wt.HWND]
    user.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
    user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user.AttachThreadInput.argtypes = [wt.DWORD, wt.DWORD, wt.BOOL]
    user.BringWindowToTop.argtypes = [wt.HWND]
    user.MapVirtualKeyW.argtypes = [wt.UINT, wt.UINT]
    user.IsWindow.argtypes = [wt.HWND]
    user.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]

TAG = 0x4F4641   # marks OFA-injected input so OFA's own hooks can ignore it


@dataclass
class El:
    id: str
    text: str
    role: str
    bbox: tuple[int, int, int, int]
    source: str = "uia"
    enabled: bool = True
    is_password: bool = False
    value: str | None = None
    automation_id: str = ""
    focusable: bool = False
    node: object = field(default=None, repr=False, compare=False)

    def center(self) -> tuple[int, int]:
        l, t, r, b = self.bbox
        return (l + r) // 2, (t + b) // 2

    def public(self) -> str:
        """Compact one-line form for the engine: id role "text" =value [flags]."""
        parts = [self.id, self.role.replace(" ", "_")]
        if self.text:
            parts.append('"' + self.text[:80].replace('"', "'") + '"')
        if self.value and not self.is_password and self.value != self.text:
            parts.append("=" + repr(self.value[:120]))
        if self.is_password:
            parts.append("[password]")
        if not self.enabled:
            parts.append("[disabled]")
        return " ".join(parts)


# --- windows & processes ---------------------------------------------------------------------
def list_windows() -> list[dict]:
    out = []
    for w in _windows():
        ident = process_identity(w["pid"]) or {}
        exe = ident.get("executable", "")
        cls = ctypes.create_unicode_buffer(256)
        user.GetClassNameW(w["window"], cls, 256)
        if cls.value in {"Progman", "WorkerW", "Shell_TrayWnd"}:
            continue
        rect = wt.RECT()
        user.GetWindowRect(w["window"], ctypes.byref(rect))
        if rect.right - rect.left < 50 or rect.bottom - rect.top < 30:
            continue
        out.append({"hwnd": int(w["window"]), "title": w["title"], "pid": w["pid"], "exe": exe,
                    "process": os.path.basename(exe).lower(), "class": cls.value,
                    "rect": (rect.left, rect.top, rect.right, rect.bottom), "minimized": bool(user.IsIconic(w["window"]))})
    return out


def foreground() -> int:
    return int(user.GetForegroundWindow() or 0)


def focus(hwnd: int) -> bool:
    """Bring a window to the front, escalating through the documented foreground-lock workarounds.
    Success is judged only by GetForegroundWindow afterwards."""
    if foreground() == hwnd:
        return True
    if user.IsIconic(hwnd):
        user.ShowWindow(hwnd, 9)
    cur = kernel.GetCurrentThreadId()

    def attempt() -> bool:
        fg = user.GetForegroundWindow()
        other = user.GetWindowThreadProcessId(fg, None) if fg else 0
        target = user.GetWindowThreadProcessId(hwnd, None)
        attached = []
        for t in {other, target} - {0, cur}:
            if user.AttachThreadInput(cur, t, True):
                attached.append(t)
        try:
            _key_event(0x12, False)
            _key_event(0x12, True)
            user.BringWindowToTop(hwnd)
            user.SetForegroundWindow(hwnd)
        finally:
            for t in attached:
                user.AttachThreadInput(cur, t, False)
        time.sleep(0.12)
        return foreground() == hwnd

    if attempt():
        return True
    user.SwitchToThisWindow.argtypes = [wt.HWND, wt.BOOL]
    user.SwitchToThisWindow(hwnd, True)
    time.sleep(0.2)
    if foreground() == hwnd:
        return True
    user.ShowWindow(hwnd, 6)      # minimize then restore: Windows grants foreground on restore
    time.sleep(0.15)
    user.ShowWindow(hwnd, 9)
    time.sleep(0.25)
    return attempt() or foreground() == hwnd


def show(hwnd: int, how: str) -> None:
    user.ShowWindow(hwnd, {"minimize": 6, "maximize": 3, "restore": 9}[how])


def close_window(hwnd: int) -> None:
    user.PostMessageW(hwnd, 0x0010, 0, 0)   # WM_CLOSE; unsaved-changes dialogs stay with the user


def window_exists(hwnd: int) -> bool:
    return bool(user.IsWindow(hwnd))


def move(hwnd: int, rect: tuple[int, int, int, int]) -> None:
    user.MoveWindow.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.BOOL]
    l, t, r, b = rect
    user.ShowWindow(hwnd, 9)
    user.MoveWindow(hwnd, l, t, r - l, b - t, True)


def work_area() -> tuple[int, int, int, int]:
    rect = wt.RECT()
    user.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
    return rect.left, rect.top, rect.right, rect.bottom


# --- input ----------------------------------------------------------------------------------
def _send(events: list[Input]) -> None:
    arr = (Input * len(events))(*events)
    if user.SendInput(len(events), arr, ctypes.sizeof(Input)) != len(events):
        raise PermissionError("Windows blocked input (the target may be elevated or on the secure desktop)")


def _key_event(vk: int, up: bool) -> None:
    flags = 0x0002 if up else 0
    if vk in {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0x5B}:
        flags |= 0x0001    # extended
    _send([Input(type=1, ki=KeyInput(vk, user.MapVirtualKeyW(vk, 0), flags, 0, TAG))])


def type_unicode(text: str, delay: float = 0.004) -> None:
    for ch in text:
        if ch == "\n":
            press("shift+enter")
            continue
        units = ch.encode("utf-16-le")
        for i in range(0, len(units), 2):
            unit = int.from_bytes(units[i:i + 2], "little")
            _send([Input(type=1, ki=KeyInput(0, unit, 0x0004, 0, TAG)),
                   Input(type=1, ki=KeyInput(0, unit, 0x0006, 0, TAG))])
        if delay:
            time.sleep(delay)


VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B, "enter": 0x0D, "return": 0x0D,
      "tab": 0x09, "esc": 0x1B, "escape": 0x1B, "backspace": 0x08, "delete": 0x2E, "del": 0x2E, "space": 0x20,
      "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27, "home": 0x24, "end": 0x23, "pageup": 0x21,
      "pagedown": 0x22, "insert": 0x2D, **{f"f{i}": 0x6F + i for i in range(1, 13)}}


def press(combo: str) -> None:
    keys = [k.strip().lower() for k in combo.replace("-", "+").split("+") if k.strip()]
    codes = []
    for k in keys:
        if k in VK:
            codes.append(VK[k])
        elif len(k) == 1:
            res = user.VkKeyScanW(ord(k))
            codes.append(res & 0xFF)
        else:
            raise ValueError(f"Unknown key {k!r}")
    for c in codes:
        _key_event(c, False)
    for c in reversed(codes):
        _key_event(c, True)
    time.sleep(0.05)


def click_at(x: int, y: int, button: str = "left", double: bool = False) -> None:
    user.SetCursorPos(int(x), int(y))
    down, up = (0x0002, 0x0004) if button == "left" else (0x0008, 0x0010)
    for _ in range(2 if double else 1):
        _send([Input(type=0, mi=MouseInput(0, 0, 0, down, 0, TAG)), Input(type=0, mi=MouseInput(0, 0, 0, up, 0, TAG))])
        time.sleep(0.05)


def drag(a: tuple[int, int], b: tuple[int, int]) -> None:
    user.SetCursorPos(*a)
    _send([Input(type=0, mi=MouseInput(0, 0, 0, 0x0002, 0, TAG))])
    for i in range(1, 11):
        user.SetCursorPos(a[0] + (b[0] - a[0]) * i // 10, a[1] + (b[1] - a[1]) * i // 10)
        time.sleep(0.02)
    _send([Input(type=0, mi=MouseInput(0, 0, 0, 0x0004, 0, TAG))])


def wheel(x: int, y: int, clicks: int) -> None:
    user.SetCursorPos(int(x), int(y))
    _send([Input(type=0, mi=MouseInput(0, 0, ctypes.c_uint32(clicks * 120).value, 0x0800, 0, TAG))])
    time.sleep(0.15)


# --- UIA ------------------------------------------------------------------------------------
_local = threading.local()


def automation():
    if not hasattr(_local, "uia"):
        import comtypes
        import comtypes.client
        comtypes.CoInitialize()
        mod = comtypes.client.GetModule("UIAutomationCore.dll")
        _local.mod = mod
        _local.uia = comtypes.client.CreateObject(mod.CUIAutomation, interface=mod.IUIAutomation)
    return _local.uia, _local.mod


INTERESTING = {"button", "edit", "document", "hyperlink", "link", "list item", "menu item", "tab item", "check box",
               "radio button", "combo box", "tree item", "text", "item", "data item", "split button", "menu bar",
               "toolbar", "group", "list", "heading", "image", "pane", "cell", "header item", "toggle button"}


def uia_tree(hwnd: int, max_nodes: int = 2500, max_depth: int = 30, budget_s: float = 2.5) -> tuple[list[El], bool]:
    uia, mod = automation()
    root = uia.ElementFromHandle(hwnd)
    walker = uia.ControlViewWalker
    out: list[El] = []
    stack = [(root, 0)]
    complete, start, n = True, time.monotonic(), 0
    while stack:
        node, depth = stack.pop()
        n += 1
        if n > max_nodes or time.monotonic() - start > budget_s:
            complete = False
            break
        try:
            r = node.CurrentBoundingRectangle
            bbox = (r.left, r.top, r.right, r.bottom)
            role = str(node.CurrentLocalizedControlType or "").lower()
            name = str(node.CurrentName or "").strip()
            pw = bool(node.CurrentIsPassword)
            value = None
            if not pw and role in {"edit", "combo box", "document", "text"}:
                try:
                    pat = node.GetCurrentPattern(10002)
                    if pat:
                        value = str(pat.QueryInterface(mod.IUIAutomationValuePattern).CurrentValue)[:2000]
                except Exception:
                    pass
            visible = bbox[2] > bbox[0] and bbox[3] > bbox[1] and not node.CurrentIsOffscreen
            if visible and (name or value or role in {"edit", "document"}) and role in INTERESTING:
                out.append(El(id=f"u{len(out)}", text=name, role=role, bbox=bbox, enabled=bool(node.CurrentIsEnabled),
                              is_password=pw, value=None if pw else value,
                              automation_id=str(node.CurrentAutomationId or ""),
                              focusable=bool(node.CurrentIsKeyboardFocusable), node=node))
            if depth < max_depth:
                kids = []
                child = walker.GetFirstChildElement(node)
                while child and len(kids) < 400:
                    kids.append(child)
                    child = walker.GetNextSiblingElement(child)
                stack.extend((k, depth + 1) for k in reversed(kids))
        except Exception:
            continue
    return out, complete


def uia_invoke(el: El) -> bool:
    _, mod = automation()
    for pid, iface, call in ((10000, "IUIAutomationInvokePattern", "Invoke"),
                             (10010, "IUIAutomationSelectionItemPattern", "Select"),
                             (10015, "IUIAutomationTogglePattern", "Toggle"),
                             (10005, "IUIAutomationExpandCollapsePattern", "Expand")):
        try:
            pat = el.node.GetCurrentPattern(pid)
            if pat:
                getattr(pat.QueryInterface(getattr(mod, iface)), call)()
                return True
        except Exception:
            continue
    return False


def uia_set_value(el: El, text: str) -> bool:
    _, mod = automation()
    try:
        pat = el.node.GetCurrentPattern(10002)
        if pat:
            vp = pat.QueryInterface(mod.IUIAutomationValuePattern)
            if not vp.CurrentIsReadOnly:
                vp.SetValue(text)
                return True
    except Exception:
        pass
    return False


def uia_focus(el: El) -> bool:
    try:
        el.node.SetFocus()
        return True
    except Exception:
        return False


def uia_value(el: El) -> str | None:
    _, mod = automation()
    try:
        pat = el.node.GetCurrentPattern(10002)
        if pat:
            return str(pat.QueryInterface(mod.IUIAutomationValuePattern).CurrentValue)
    except Exception:
        pass
    try:
        pat = el.node.GetCurrentPattern(10014)   # TextPattern
        if pat:
            return str(pat.QueryInterface(mod.IUIAutomationTextPattern).DocumentRange.GetText(20000))
    except Exception:
        pass
    return None


def focused_element() -> El | None:
    uia, _ = automation()
    try:
        node = uia.GetFocusedElement()
        r = node.CurrentBoundingRectangle
        return El("focus", str(node.CurrentName or ""), str(node.CurrentLocalizedControlType or "").lower(),
                  (r.left, r.top, r.right, r.bottom), is_password=bool(node.CurrentIsPassword), node=node)
    except Exception:
        return None


# --- capture & OCR --------------------------------------------------------------------------
def capture(rect: tuple[int, int, int, int]) -> tuple[bytes, int, int]:
    """Raw BGRA pixels of a screen rectangle (the window must be visible)."""
    import mss
    l, t, r, b = rect
    with mss.mss() as s:
        shot = s.grab({"left": l, "top": t, "width": max(1, r - l), "height": max(1, b - t)})
        return bytes(shot.bgra), shot.width, shot.height


def to_png(bgra: bytes, w: int, h: int) -> bytes:
    import mss.tools
    rgb = bytearray(w * h * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = bgra[2::4], bgra[1::4], bgra[0::4]
    return mss.tools.to_png(bytes(rgb), (w, h))


def ocr(bgra: bytes, w: int, h: int, origin: tuple[int, int] = (0, 0)) -> list[El]:
    import asyncio
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapPixelFormat, SoftwareBitmap
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter

    async def run():
        engine = OcrEngine.try_create_from_user_profile_languages()
        if engine is None:
            return []
        writer = DataWriter()
        writer.write_bytes(list(bgra) if not isinstance(bgra, (bytes, bytearray)) else bgra)
        buf = writer.detach_buffer()
        bmp = SoftwareBitmap.create_copy_from_buffer(buf, BitmapPixelFormat.BGRA8, w, h, BitmapAlphaMode.PREMULTIPLIED)
        result = await engine.recognize_async(bmp)
        out = []
        for i, line in enumerate(result.lines):
            words = list(line.words)
            if not words:
                continue
            xs = [wd.bounding_rect.x for wd in words]
            ys = [wd.bounding_rect.y for wd in words]
            x2 = [wd.bounding_rect.x + wd.bounding_rect.width for wd in words]
            y2 = [wd.bounding_rect.y + wd.bounding_rect.height for wd in words]
            out.append(El(f"o{i}", line.text, "text", (int(min(xs)) + origin[0], int(min(ys)) + origin[1],
                                                       int(max(x2)) + origin[0], int(max(y2)) + origin[1]), "ocr"))
        return out
    return asyncio.run(run())


def ocr_languages() -> list[str]:
    try:
        from winrt.windows.media.ocr import OcrEngine
        return [l.language_tag for l in OcrEngine.available_recognizer_languages]
    except Exception:
        return []


# --- apps -----------------------------------------------------------------------------------
_apps_cache: tuple[float, list[dict]] = (0.0, [])


def installed_apps(refresh: bool = False) -> list[dict]:
    global _apps_cache
    if not refresh and time.monotonic() - _apps_cache[0] < 600 and _apps_cache[1]:
        return _apps_cache[1]
    apps: list[dict] = []
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "Get-StartApps | ForEach-Object { $_.Name + '|' + $_.AppID }"],
                             capture_output=True, text=True, timeout=25, creationflags=0x08000000)
        for line in out.stdout.splitlines():
            if "|" in line:
                name, appid = line.rsplit("|", 1)
                apps.append({"name": name.strip(), "appid": appid.strip(), "source": "start"})
    except Exception:
        pass
    from ofa_execution.windows import discover_apps
    for a in discover_apps():
        apps.append({"name": os.path.splitext(a["name"])[0], "exe": a["executable"], "source": "app_paths"})
    _apps_cache = (time.monotonic(), apps)
    return apps


def launch(app: dict) -> None:
    if app.get("appid"):
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app['appid']}"], creationflags=0x08000000)
    elif app.get("exe"):
        subprocess.Popen([app["exe"]], creationflags=0x00000008 | 0x00000200)
    else:
        raise FileNotFoundError(app.get("name"))


def open_uri(uri: str) -> None:
    os.startfile(uri)  # noqa: S606 — URIs/paths validated by the hands graph before this call
