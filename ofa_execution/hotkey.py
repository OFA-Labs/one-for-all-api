"""Emergency stop independent from HTTP, planners and voice."""
import ctypes
import os
import threading
from ctypes import wintypes


class StopHotkey:
    def __init__(self, stop):
        self.stop = stop
        self.available = False
        self.thread_id = None
        self.ready = threading.Event()

    def start(self):
        if os.name != "nt":
            return self
        def run():
            user = ctypes.windll.user32
            self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
            self.available = bool(user.RegisterHotKey(None, 0x4F46, 0x4000 | 1 | 4, ord("J")))
            self.ready.set()
            if not self.available:
                return
            msg = wintypes.MSG()
            try:
                while user.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                    if msg.message == 0x0312:
                        self.stop()
            finally:
                user.UnregisterHotKey(None, 0x4F46)
        threading.Thread(target=run, name="ofa-stop-hotkey", daemon=True).start()
        self.ready.wait(2)
        return self

    def close(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, 0x0012, 0, 0)
