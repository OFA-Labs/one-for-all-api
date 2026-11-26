"""Glowing orb, top-middle, always on top, click-through (C1). Seven states + mic-live ring + caption.
The caption also shows the exact pending item during an approval (§6 'show the exact item')."""
from __future__ import annotations

import ctypes
import math
import os
import queue
import tkinter as tk

STATES = {
    "idle": ("#4b5563", "Idle"), "listening": ("#22d3ee", "Listening"), "thinking": ("#a78bfa", "Thinking"),
    "acting": ("#34d399", "Working"), "speaking": ("#60a5fa", "Speaking"),
    "awaiting_approval": ("#fbbf24", "Waiting for your yes or no"), "error": ("#f87171", "Needs attention"),
}


class Orb:
    def __init__(self, on_close=lambda: None):
        self.q: queue.Queue = queue.Queue(64)
        if os.name == "nt":
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError, OSError):
                pass
        self.root = tk.Tk()
        self.root.title("OFA")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.key = "#010203"
        self.root.configure(bg=self.key)
        if os.name == "nt":
            self.root.attributes("-transparentcolor", self.key)
        self.w, self.h = 520, 150
        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"{self.w}x{self.h}+{(sw - self.w) // 2}+8")
        self.c = tk.Canvas(self.root, width=self.w, height=self.h, bg=self.key, highlightthickness=0)
        self.c.pack()
        self.cx, self.cy, self.r = self.w // 2, 40, 22
        self.glow = [self.c.create_oval(0, 0, 0, 0, outline="", fill="") for _ in range(4)]
        self.core = self.c.create_oval(0, 0, 0, 0, outline="", fill="#4b5563")
        self.ring = self.c.create_oval(self.cx - 31, self.cy - 31, self.cx + 31, self.cy + 31, outline="", width=2)
        self.caption_bg = self.c.create_rectangle(10, 78, self.w - 10, 146, fill="#0b0f17", outline="#1f2937")
        self.caption = self.c.create_text(self.cx, 112, text="", fill="#e5e7eb", width=self.w - 36,
                                          font=("Segoe UI", 10), justify="center")
        self.state, self.mic, self.t = "idle", False, 0.0
        self.on_close = on_close
        self.root.update_idletasks()
        self._click_through()
        self.root.withdraw()
        self.root.after(33, self._tick)
        self.root.after(30, self._pump)

    def _click_through(self):
        if os.name != "nt":
            return
        hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
        style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
        # WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x08000000 | 0x80)

    # thread-safe API -------------------------------------------------------------------------
    def set(self, state: str, caption: str | None = None, mic: bool | None = None) -> None:
        try:
            self.q.put_nowait((state, caption, mic))
        except queue.Full:
            pass

    def close(self) -> None:
        self.set("__quit__")

    # tk thread -----------------------------------------------------------------------------
    def _pump(self):
        try:
            while True:
                state, caption, mic = self.q.get_nowait()
                if state == "__quit__":
                    self.root.quit()
                    return
                if mic is not None:
                    self.mic = mic
                if state:
                    self.state = state
                    if state == "idle" and not self.mic:
                        self.root.withdraw()
                    else:
                        self.root.deiconify()
                        self.root.attributes("-topmost", True)
                if caption is not None:
                    text = caption[:300]
                    self.c.itemconfigure(self.caption, text=text)
                    self.c.itemconfigure(self.caption_bg, state="normal" if text else "hidden")
        except queue.Empty:
            pass
        self.root.after(30, self._pump)

    def _tick(self):
        self.t += 0.033
        color, _ = STATES.get(self.state, STATES["idle"])
        speed = {"listening": 2.2, "thinking": 4.0, "acting": 3.0, "speaking": 5.0, "awaiting_approval": 1.6}.get(self.state, 0.8)
        pulse = (math.sin(self.t * speed) + 1) / 2
        r = self.r + pulse * (5 if self.state != "idle" else 1)
        for i, g in enumerate(self.glow):
            gr = r + 6 + i * 5 + pulse * 3
            self.c.coords(g, self.cx - gr, self.cy - gr, self.cx + gr, self.cy + gr)
            self.c.itemconfigure(g, fill=self._mix(color, self.key, 0.18 + 0.12 * (3 - i) / 3 * (0.6 + 0.4 * pulse)))
        self.c.coords(self.core, self.cx - r, self.cy - r, self.cx + r, self.cy + r)
        self.c.itemconfigure(self.core, fill=color)
        self.c.itemconfigure(self.ring, outline="#ef4444" if self.mic else "")
        self.root.after(33, self._tick)

    @staticmethod
    def _mix(a: str, b: str, t: float) -> str:
        ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{int(x * t + y * (1 - t)):02x}" for x, y in zip(ca, cb))

    def run(self):
        self.root.mainloop()


class NullOrb:
    def __init__(self):
        self.history: list[tuple] = []

    def set(self, state, caption=None, mic=None):
        self.history.append((state, caption, mic))

    def close(self):
        pass
