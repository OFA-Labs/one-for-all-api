"""Caps-only physical global hook; preserve the executor's emergency hotkey."""
from __future__ import annotations

import ctypes
import os
import threading
from collections.abc import Callable
from ctypes import wintypes as wt


class CapsHook:
    def __init__(self, toggle: Callable[[], None], enabled: Callable[[], bool] = lambda: True) -> None:
        self.toggle = toggle
        self.enabled = enabled
        self.available = False
        self._thread_id = 0
        self._ready = threading.Event()
        self._held = False

    def start(self) -> CapsHook:
        if os.name != "nt":
            return self
        threading.Thread(target=self._run, daemon=True, name="ofa-caps").start()
        self._ready.wait(2)
        return self

    def _run(self) -> None:
        user = ctypes.WinDLL("user32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, ctypes.c_int, wt.WPARAM, wt.LPARAM
        )

        class Key(ctypes.Structure):
            _fields_ = [
                ("key", wt.DWORD), ("scan", wt.DWORD),
                ("flags", wt.DWORD), ("time", wt.DWORD),
                ("extra", ctypes.c_size_t),
            ]

        user.SetWindowsHookExW.argtypes = [
            ctypes.c_int, callback_type, wt.HINSTANCE, wt.DWORD
        ]
        user.SetWindowsHookExW.restype = wt.HANDLE
        user.CallNextHookEx.argtypes = [
            wt.HANDLE, ctypes.c_int, wt.WPARAM, wt.LPARAM
        ]
        user.CallNextHookEx.restype = ctypes.c_ssize_t
        kernel.GetModuleHandleW.restype = wt.HMODULE
        self._thread_id = kernel.GetCurrentThreadId()

        @callback_type
        def callback(code: int, message: int, pointer: int) -> int:
            if code >= 0:
                event = ctypes.cast(pointer, ctypes.POINTER(Key)).contents
                if event.key == 0x14 and not event.flags & 0x10:
                    if message in {0x0101, 0x0105} and self._held:
                        self._held = False
                        return 1
                    modified = any(user.GetAsyncKeyState(k) & 0x8000
                                   for k in (0x10, 0x11, 0x12, 0x5B, 0x5C))
                    if message in {0x0100, 0x0104} and not modified and self.enabled():
                        if not self._held:
                            self._held = True
                            self.toggle()
                        return 1
            return user.CallNextHookEx(None, code, message, pointer)

        hook = user.SetWindowsHookExW(13, callback, kernel.GetModuleHandleW(None), 0)
        self.available = bool(hook)
        self._ready.set()
        try:
            if hook:
                message = wt.MSG()
                while user.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                    user.TranslateMessage(ctypes.byref(message))
                    user.DispatchMessageW(ctypes.byref(message))
        finally:
            user.UnhookWindowsHookEx.argtypes = [wt.HANDLE]
            if hook:
                user.UnhookWindowsHookEx(hook)

    def close(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, 0x0012, 0, 0)
