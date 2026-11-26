"""Windows effector: verified processes/windows, bounded UIA and real input.

UIA is optional at import; unsupported hosts report capabilities accurately.
No elevation, terminal, password manager or arbitrary shell execution.
"""
from __future__ import annotations

import base64
import ctypes
import os
import struct
import threading
import time
from ctypes import wintypes as wt
from pathlib import Path

from .contracts import Element, Evidence, ExecutionError, Observation, Outcome, digest
from .verification import verify


IS_WINDOWS = os.name == "nt"
if IS_WINDOWS:
    user = ctypes.WinDLL("user32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    user.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
    user.GetWindowTextLengthW.argtypes = [wt.HWND]
    user.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
    user.IsWindow.argtypes = [wt.HWND]
    user.IsWindowVisible.argtypes = [wt.HWND]
    user.GetForegroundWindow.restype = wt.HWND
    user.SetForegroundWindow.argtypes = [wt.HWND]
    user.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    kernel.GetProcessTimes.argtypes = [wt.HANDLE, ctypes.POINTER(wt.FILETIME), ctypes.POINTER(wt.FILETIME), ctypes.POINTER(wt.FILETIME), ctypes.POINTER(wt.FILETIME)]
    kernel.CloseHandle.argtypes = [wt.HANDLE]


def process_identity(pid):
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        name, size = ctypes.create_unicode_buffer(32768), wt.DWORD(32768)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            return None
        times = [wt.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return {"pid": pid, "executable": str(Path(name.value).resolve()),
                "started": (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime}
    finally:
        kernel.CloseHandle(handle)


def windows():
    if not IS_WINDOWS:
        return []
    results = []
    callback_type = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    @callback_type
    def callback(hwnd, _):
        if user.IsWindowVisible(hwnd):
            length = user.GetWindowTextLengthW(hwnd)
            if length:
                title = ctypes.create_unicode_buffer(length + 1)
                user.GetWindowTextW(hwnd, title, length + 1)
                pid = wt.DWORD()
                user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                results.append({"window": int(hwnd), "title": title.value, "pid": pid.value})
        return True
    user.EnumWindows.argtypes = [callback_type, wt.LPARAM]
    user.EnumWindows(callback, 0)
    return results


def discover_apps():
    """Metadata only; discovery does not grant allowlist permission."""
    if not IS_WINDOWS:
        return []
    import winreg
    found = []
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths") as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    name = winreg.EnumKey(root, i)
                    try:
                        with winreg.OpenKey(root, name) as item:
                            path = winreg.QueryValue(item, None).strip('"')
                            if Path(path).is_file():
                                found.append({"name": name, "executable": path, "source": "App Paths"})
                    except OSError:
                        pass
        except OSError:
            pass
    return found


class DesktopHand:
    def __init__(self, config):
        self.config = config
        self._local = threading.local()
        self.owned_processes = []
        self.active_window = None
        self._cli_records = {}

    def capabilities(self):
        import importlib.util
        available = IS_WINDOWS and importlib.util.find_spec("comtypes") is not None
        return {"hand": "desktop", "available": available,
                "operations": ["app.open", "window.observe", "window.focus", "window.minimize", "window.maximize", "window.restore", "desktop.click", "desktop.fill", "desktop.type", "desktop.scroll", "desktop.screenshot"] if available else [],
                "vision": "future_integration", "discovery": "App Paths; explicit executable allowlist"}

    def _automation(self):
        if not self.capabilities()["available"]:
            raise ExecutionError("UIA_UNAVAILABLE", "Windows and the optional pinned comtypes dependency are required for native UIA.")
        if not hasattr(self._local, "automation"):
            import comtypes
            import comtypes.client
            comtypes.CoInitialize()
            module = comtypes.client.GetModule("UIAutomationCore.dll")
            self._local.module = module
            self._local.automation = comtypes.client.CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
        return self._local.automation, self._local.module

    def _find(self, app, allow_multiple=False):
        if app.launch_kind == "interactive_command":
            from .native_launch import descendants, process_parents, application_identity
            record = self._cli_records.get(app.launch_identity)
            if not record: return None
            candidates = [w for w in windows() if w["title"] == record["title"]]
            parents = process_parents()
            for window in candidates:
                package = application_identity(window["pid"]) or ""
                if not package.startswith("Microsoft.WindowsTerminal_"): continue
                children = [process_identity(pid) for pid in descendants(window["pid"],parents)]
                matched = [p for p in children if p and p["started"]>=record["started"] and
                           Path(p["executable"]).resolve()==Path(app.executable).resolve()]
                if matched:
                    return {**window,**matched[0],"console_pid":window["pid"],"launch_title":record["title"]}
            return None
        matches = []
        for item in windows():
            if app.window_title and item["title"] != app.window_title:
                continue
            identity = process_identity(item["pid"])
            if app.launch_kind == "aumid":
                from .native_launch import application_identity
                matched = identity and application_identity(item["pid"]) == app.launch_identity
            else:
                matched = identity and Path(identity["executable"]) == Path(app.executable).resolve()
            if matched:
                matches.append({**item, **identity})
        if len(matches) > 1 and not allow_multiple:
            raise ExecutionError("WINDOW_AMBIGUOUS", "More than one allowed app window matches; configure an exact window title.")
        return matches[0] if matches else None

    def observe(self, step):
        app = self.config.app(step.target.app or "")
        lightweight = step.operation in {"app.open","window.focus","window.minimize","window.maximize","window.restore","window.close"}
        window = self._find(app, allow_multiple=step.operation in {"app.open","window.focus","window.minimize","window.maximize","window.restore"})
        if not window:
            if step.operation in {"app.open","window.close"}:
                return Observation(surface="desktop", identity={"app": app.name}, facts={"opened": False,"closed":True})
            raise ExecutionError("WINDOW_NOT_FOUND", "Open the allowed app before interacting with it.")
        if lightweight:
            return Observation(surface="desktop", identity={"app": app.name, **window},
                               facts={"opened": True})
        automation, module = self._automation()
        root = automation.ElementFromHandle(window["window"])
        self.active_window = window["window"]
        tree = []
        nodes = {}
        stack = [(root, 0)]
        walker = automation.ControlViewWalker
        complete = True
        while stack:
            node, depth = stack.pop()
            if len(tree) >= 300 or depth > 12:
                complete = False
                break
            try:
                protected = bool(node.CurrentIsPassword)
                role = str(node.CurrentLocalizedControlType).lower()
                name = str(node.CurrentName or "")
                if any(x in name.lower() for x in ("password", "one-time code", "verification code", "captcha")):
                    protected = True
                runtime = list(node.GetRuntimeId())
                ref = digest({"window": window, "runtime": runtime})[:24]
                rectangle = node.CurrentBoundingRectangle
                value = None
                if not protected:
                    try:
                        pattern = node.GetCurrentPattern(10002).QueryInterface(module.IUIAutomationValuePattern)
                        value = str(pattern.CurrentValue)[:16384]
                    except Exception:
                        pass
                tree.append(Element(ref=ref, name="[protected]" if protected else name[:500], role=role,
                                    value=value, protected=protected, enabled=bool(node.CurrentIsEnabled),
                                    bounds=[rectangle.left, rectangle.top, rectangle.right, rectangle.bottom],
                                    extra={"runtime": runtime, "automation_id": str(node.CurrentAutomationId or ""),
                                           "offscreen": bool(node.CurrentIsOffscreen)}))
                nodes[ref] = node
                children = []
                child = walker.GetFirstChildElement(node)
                while child:
                    children.append(child)
                    if len(children) > 300:
                        complete = False
                        break
                    child = walker.GetNextSiblingElement(child)
                stack.extend((c, depth + 1) for c in reversed(children))
            except Exception:
                complete = False
                break
        self._local.nodes = nodes
        protected = any(e.protected for e in tree)
        return Observation(surface="desktop", identity={"app": app.name, **window}, elements=tree,
                           complete=complete, facts={"opened": True, "human_required": protected})

    def _target(self, step, observation):
        elements = [e for e in observation.elements if not e.protected and e.enabled and not e.extra.get("offscreen")]
        if step.target.ref:
            elements = [e for e in elements if e.ref == step.target.ref]
        else:
            if step.target.name is not None:
                elements = [e for e in elements if e.name.casefold() == step.target.name.casefold()]
            if step.target.role:
                elements = [e for e in elements if e.role.casefold() == step.target.role.casefold()]
        if not elements:
            raise ExecutionError("TARGET_NOT_FOUND", "No structural element matches; no coordinate guess will be attempted.")
        if len(elements) != 1:
            raise ExecutionError("TARGET_AMBIGUOUS", "Choose the exact element.",
                                 [{"id": e.ref, "label": f"{e.role}: {e.name}"} for e in elements[:20]])
        return elements[0], self._local.nodes[elements[0].ref]

    def validate_target(self, step, before):
        if step.operation.startswith("desktop.") and step.operation != "desktop.screenshot" and not before.facts.get("human_required"):
            self._target(step, before)

    def execute(self, step, before, checkpoint):
        app = self.config.app(step.target.app or "")
        checkpoint()
        if step.operation == "window.close" and before.facts.get("closed"):
            return Outcome(status="verified",observation=before,
                evidence=[Evidence(tier="A",kind="window_closed_readback",reading_hash=before.hash)])
        if step.operation == "app.open":
            window = self._find(app, allow_multiple=True)
            if not window:
                from .native_launch import launch
                process = launch(app)
                if process is not None:
                    self.owned_processes.append(process)
                    if app.launch_kind == "interactive_command":
                        self._cli_records[app.launch_identity] = {"title":process.ofa_console_title,"started":process.ofa_started}
                deadline = time.monotonic() + (15 if app.launch_kind == "interactive_command" else 8)
                while not window and time.monotonic() < deadline:
                    checkpoint()
                    time.sleep(0.05)
                    window = self._find(app, allow_multiple=True)
            if not window:
                raise ExecutionError("LAUNCH_NOT_VERIFIED", "No matching process/window appeared after launch.")
            checkpoint()
            user.ShowWindow(window["window"], 9)
            user.SetForegroundWindow(window["window"])
            after = self.observe(step)
            return Outcome(status="verified", observation=after,
                           evidence=[Evidence(tier="A", kind="process_and_window_readback", reading_hash=after.hash)])
        if step.operation in {"window.observe", "desktop.screenshot"}:
            after = self.observe(step)
            if step.operation == "desktop.screenshot":
                if not app.capture or any(e.protected for e in after.elements):
                    raise ExecutionError("CAPTURE_NOT_ALLOWED", "Capture needs explicit app consent and no protected controls.")
                checkpoint()
                after.frame = capture_window(after.identity["window"])
            return Outcome(status="verified", observation=after,
                           evidence=[Evidence(tier="A", kind="fresh_uia", reading_hash=after.hash)])
        window = self._find(app, allow_multiple=step.operation in {"window.focus","window.minimize","window.maximize","window.restore"})
        if not window or window != {k: before.identity[k] for k in window}:
            raise ExecutionError("WINDOW_CHANGED", "The process/window identity changed.")
        if step.operation == "window.focus":
            user.ShowWindow(window["window"], 9)
            user.SetForegroundWindow(window["window"])
            if user.GetForegroundWindow() != window["window"]:
                raise ExecutionError("FOCUS_DENIED", "Windows refused foreground activation; focus it yourself.")
            after = self.observe(step)
            return Outcome(status="verified", observation=after,
                           evidence=[Evidence(tier="A", kind="foreground_readback", reading_hash=after.hash)])
        if step.operation in {"window.minimize", "window.maximize", "window.restore"}:
            user.IsIconic.argtypes = [wt.HWND]
            user.IsZoomed.argtypes = [wt.HWND]
            mode = {"window.minimize": 6, "window.maximize": 3, "window.restore": 9}[step.operation]
            user.ShowWindow(window["window"], mode)
            good = bool(user.IsIconic(window["window"])) if mode == 6 else bool(user.IsZoomed(window["window"])) if mode == 3 else not user.IsIconic(window["window"]) and not user.IsZoomed(window["window"])
            after = self.observe(step)
            return Outcome(status="verified" if good else "unknown", observation=after,
                           evidence=[Evidence(tier="A", kind="window_state_readback", reading_hash=after.hash)])
        if step.operation == "window.close":
            # WM_CLOSE preserves the application's own save/confirmation dialog.
            # Never terminate the process or answer a discard prompt.
            if self.observe(step).hash != before.hash:
                raise ExecutionError("READING_CHANGED", "The window changed after approval.")
            checkpoint()
            user.PostMessageW.argtypes=[wt.HWND,wt.UINT,wt.WPARAM,wt.LPARAM]
            if not user.PostMessageW(window["window"],0x0010,0,0):
                raise ExecutionError("CLOSE_DENIED", "Windows refused the close request.")
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                checkpoint()
                if not user.IsWindow(window["window"]):
                    after=Observation(surface="desktop",identity={"app":app.name},facts={"opened":False,"closed":True})
                    return Outcome(status="verified",observation=after,
                        evidence=[Evidence(tier="A",kind="window_closed_readback",reading_hash=after.hash)])
                time.sleep(.05)
            after=self.observe(step)
            after.facts["human_required"]=True
            after.facts["reason"]="The application needs you to resolve its save/close dialog. No data was discarded."
            return Outcome(status="handoff",observation=after)
        if not app.writable:
            raise ExecutionError("APP_READ_ONLY", "This app was consented for view/launch only.")
        fresh = self.observe(step)
        if fresh.hash != before.hash:
            raise ExecutionError("READING_CHANGED", "Native state changed after approval.")
        element, node = self._target(step, fresh)
        _, module = self._automation()
        if user.GetForegroundWindow() != window["window"]:
            raise ExecutionError("USER_TAKEOVER", "User focus changed; no input was sent.")
        checkpoint()
        if step.operation == "desktop.click":
            try:
                invoke = node.GetCurrentPattern(10000).QueryInterface(module.IUIAutomationInvokePattern)
            except Exception:
                invoke = None
            if invoke:
                invoke.Invoke()
            else:
                node.SetFocus()
                l, t, r, b = element.bounds
                if r <= l or b <= t:
                    raise ExecutionError("TARGET_NOT_VISIBLE", "Element has no visible rectangle.")
                automation, _ = self._automation()
                hit = automation.ElementFromPoint(wt.POINT((l+r)//2, (t+b)//2))
                for _ in range(8):
                    if hit and list(hit.GetRuntimeId()) == element.extra["runtime"]:
                        break
                    hit = automation.ControlViewWalker.GetParentElement(hit) if hit else None
                else:
                    raise ExecutionError("ELEMENT_OCCLUDED", "Another element covers the approved target.")
                # One identified click, never a coordinate batch or neighbour retry.
                user.SetCursorPos((l+r)//2, (t+b)//2)
                checkpoint()
                send_mouse(0x0002 | 0x0004)
        elif step.operation in {"desktop.fill", "desktop.type"}:
            if step.text is None:
                raise ExecutionError("INVALID_ACTION", "Typing needs exact text.")
            node.SetFocus()
            if step.operation == "desktop.fill":
                try:
                    pattern = node.GetCurrentPattern(10002).QueryInterface(module.IUIAutomationValuePattern)
                except Exception:
                    pattern = None
                if pattern:
                    checkpoint()
                    pattern.SetValue(step.text)
                else:
                    raise ExecutionError("UNSUPPORTED_CONTROL", "Replace requires an accessible Value pattern; human help is required.")
            else:
                for unit in struct.unpack('<' + 'H' * (len(step.text.encode('utf-16-le'))//2), step.text.encode('utf-16-le')):
                    checkpoint()
                    if user.GetForegroundWindow() != window["window"]:
                        raise ExecutionError("USER_TAKEOVER", "Focus changed during typing; remaining input suppressed.")
                    send_unicode(unit)
        elif step.operation == "desktop.scroll":
            try:
                scroll = node.GetCurrentPattern(10004).QueryInterface(module.IUIAutomationScrollPattern)
                scroll.Scroll(2, 1 if step.direction == "up" else 3)
            except Exception as exc:
                raise ExecutionError("UNSUPPORTED_CONTROL", "This element has no supported scroll pattern.") from exc
        else:
            raise ExecutionError("UNSUPPORTED_OPERATION", "Native operation is not implemented.")
        time.sleep(0.05)
        return verify(step, before, self.observe(step))


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("data", wt.DWORD), ("flags", wt.DWORD),
                ("time", wt.DWORD), ("extra", ctypes.c_size_t)]


class KeyInput(ctypes.Structure):
    _fields_ = [("vk", wt.WORD), ("scan", wt.WORD), ("flags", wt.DWORD), ("time", wt.DWORD), ("extra", ctypes.c_size_t)]


class InputUnion(ctypes.Union):
    _fields_ = [("mi", MouseInput), ("ki", KeyInput)]


class Input(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wt.DWORD), ("u", InputUnion)]


def send_unicode(unit):
    events = (Input * 2)(Input(type=1, ki=KeyInput(0, unit, 4, 0, 0x4F4641)),
                         Input(type=1, ki=KeyInput(0, unit, 6, 0, 0x4F4641)))
    if user.SendInput(2, events, ctypes.sizeof(Input)) != 2:
        raise ExecutionError("INPUT_BLOCKED", "Windows blocked real input; no elevation will be attempted.")


def send_mouse(flags):
    events = (Input * 1)(Input(type=0, mi=MouseInput(0, 0, 0, flags, 0, 0x4F4641)))
    if user.SendInput(1, events, ctypes.sizeof(Input)) != 1:
        raise ExecutionError("INPUT_BLOCKED", "Windows blocked mouse input.")


def capture_window(hwnd):
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    user.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
    user.GetWindowDC.argtypes, user.GetWindowDC.restype = [wt.HWND], wt.HDC
    user.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
    user.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
    gdi.CreateCompatibleDC.argtypes, gdi.CreateCompatibleDC.restype = [wt.HDC], wt.HDC
    gdi.CreateCompatibleBitmap.argtypes, gdi.CreateCompatibleBitmap.restype = [wt.HDC, ctypes.c_int, ctypes.c_int], wt.HBITMAP
    gdi.SelectObject.argtypes, gdi.SelectObject.restype = [wt.HDC, wt.HANDLE], wt.HANDLE
    gdi.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, wt.LPVOID, wt.LPVOID, wt.UINT]
    gdi.DeleteObject.argtypes, gdi.DeleteDC.argtypes = [wt.HANDLE], [wt.HDC]
    rect = wt.RECT()
    user.GetWindowRect(hwnd, ctypes.byref(rect))
    width, height = rect.right-rect.left, rect.bottom-rect.top
    if width <= 0 or height <= 0 or width*height*4 > 2*1024*1024:
        raise ExecutionError("CAPTURE_LIMIT", "Window capture exceeds the bounded frame budget.")
    dc = user.GetWindowDC(hwnd)
    memory = gdi.CreateCompatibleDC(dc)
    bitmap = gdi.CreateCompatibleBitmap(dc, width, height)
    old = gdi.SelectObject(memory, bitmap)
    try:
        if not user.PrintWindow(hwnd, memory, 2):
            raise ExecutionError("CAPTURE_UNAVAILABLE", "Window cannot be captured safely; no screen-wide fallback.")
        header = struct.pack('<IiiHHIIiiII', 40, width, -height, 1, 32, 0, width*height*4, 0, 0, 0, 0)
        info = ctypes.create_string_buffer(header)
        pixels = ctypes.create_string_buffer(width*height*4)
        if not gdi.GetDIBits(memory, bitmap, 0, height, pixels, info, 0):
            raise ExecutionError("CAPTURE_UNAVAILABLE", "Unable to read the target window frame.")
        bmp = struct.pack('<2sIHHI', b'BM', 54+len(pixels.raw), 0, 0, 54) + header + pixels.raw
        return 'data:image/bmp;base64,' + base64.b64encode(bmp).decode()
    finally:
        gdi.SelectObject(memory, old)
        gdi.DeleteObject(bitmap)
        gdi.DeleteDC(memory)
        user.ReleaseDC(hwnd, dc)
