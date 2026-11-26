"""Native top-middle status; the browser retains the existing OFA orb media."""
from __future__ import annotations

import ctypes
import os
import queue
import tkinter as tk
from tkinter import messagebox, filedialog
from collections.abc import Callable


class Overlay:
    def __init__(self, stop: Callable[[], None]) -> None:
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue(32)
        self.prompts: queue.Queue = queue.Queue(4)
        self.scope_prompts: queue.Queue = queue.Queue(2)
        self.root = tk.Tk()
        self.root.title("OFA voice")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.root.configure(bg="#071426")
        width = self.root.winfo_screenwidth()
        self.root.geometry(f"340x96+{(width - 340) // 2}+24")
        self.canvas = tk.Canvas(
            self.root, width=340, height=58, bg="#071426", highlightthickness=0
        )
        self.canvas.pack()
        self.label = tk.Label(
            self.root, text="OFA ready", bg="#071426", fg="#ccecff",
            font=("Segoe UI", 10), wraplength=330,
        )
        self.label.pack()
        self.root.protocol("WM_DELETE_WINDOW", stop)
        self.root.update_idletasks()
        self._nonactivating()
        self.root.withdraw()

    def _nonactivating(self) -> None:
        if os.name != "nt":
            return
        from ctypes import wintypes as wt
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetParent.argtypes = [wt.HWND]
        user.GetParent.restype = wt.HWND
        get_style = user.GetWindowLongPtrW
        get_style.argtypes = [wt.HWND, ctypes.c_int]
        get_style.restype = ctypes.c_ssize_t
        set_style = user.SetWindowLongPtrW
        set_style.argtypes = [wt.HWND, ctypes.c_int, ctypes.c_ssize_t]
        set_style.restype = ctypes.c_ssize_t
        hwnd = user.GetParent(self.root.winfo_id())
        set_style(hwnd, -20, get_style(hwnd, -20) | 0x08000000 | 0x20 | 0x80)

    def emit(self, state: str, text: str = "") -> None:
        if self.messages.full():
            self.messages.get_nowait()
        self.messages.put_nowait((state, text[:120]))

    def pump(self) -> None:
        if not self.scope_prompts.empty():
            kind, origin, answer = self.scope_prompts.get_nowait()
            labels={"windows":"Focus, minimize, maximize and restore ordinary application windows. Closing a window still needs a separate approval and never discards unsaved work.",
                    "read_folder":"Read bounded UTF-8 text files in a folder you select next.",
                    "write_folder":"Read and write bounded UTF-8 text files in a folder you select next. Each write requires a separate exact-content approval.",
                    "register_app":"Register one installed executable selected in the next Windows file dialog. Shells, settings, security tools and installers remain excluded.",
                    "startup_on":"Start the installed OFA companion when you sign in to Windows.",
                    "startup_off":"Remove OFA from your Windows sign-in startup items."}
            permitted=messagebox.askyesno("OFA desktop permission",f"{origin}\n\n{labels[kind]}\n\nApplies to this computer's paired OFA tabs until Disconnect.",parent=self.root)
            value=permitted
            if permitted and kind in {"read_folder","write_folder"}:
                value=filedialog.askdirectory(title="Select OFA permitted text folder",parent=self.root,mustexist=True)
            elif permitted and kind=="register_app":
                value=filedialog.askopenfilename(title="Select installed application",filetypes=[("Application","*.exe")],parent=self.root)
            answer(value)
        if not self.prompts.empty():
            origin, fingerprint, answer = self.prompts.get_nowait()
            permitted = messagebox.askyesno(
                "Connect OFA desktop",
                f"Allow {origin} to connect to this Windows computer?\n\n"
                "This grants launching installed applications and public websites. "
                "Pressing Caps Lock will send microphone audio to Deepgram (Gradium fallback). "
                "Recording stops when you press Caps Lock again or after inactivity.\n\n"
                "Connection stays paired until Disconnect. This is a local development session, "
                f"without account sign-in.\n\nBrowser key: {fingerprint}",
                parent=self.root)
            answer(permitted)
        while not self.messages.empty():
            state, text = self.messages.get_nowait()
            if state == "SHUTDOWN":
                self.root.quit()
                self.root.destroy()
                return
            if state == "IDLE":
                self.root.withdraw()
                continue
            self.root.deiconify()
            self.canvas.delete("all")
            color = "#ffb357" if state == "ERROR" else "#48bbff"
            for radius, thickness in ((26, 1), (22, 2), (17, 3), (10, 2)):
                self.canvas.create_oval(
                    170 - radius, 29 - radius, 170 + radius, 29 + radius,
                    outline=color, width=thickness,
                )
            self.label.configure(text=text or state.title())
        self.root.after(20, self.pump)

    def run(self) -> None:
        self.pump()
        self.root.mainloop()

    def request_pairing(self, origin, fingerprint, answer):
        self.prompts.put_nowait((origin, fingerprint, answer))

    def request_scope(self, kind, origin, answer):
        self.scope_prompts.put_nowait((kind,origin,answer))
