"""Native top-middle status; the browser retains the existing OFA orb media."""
from __future__ import annotations

import ctypes
import os
import queue
import json
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
from collections.abc import Callable


class Overlay:
    def __init__(self, stop: Callable[[], None]) -> None:
        self.messages: queue.Queue[tuple[str, str]] = queue.Queue(32)
        self.prompts: queue.Queue = queue.Queue(4)
        self.scope_prompts: queue.Queue = queue.Queue(2)
        if os.name=="nt":
            try: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            except (AttributeError,OSError): pass
        self.root = tk.Tk()
        self.scale = ctypes.windll.user32.GetDpiForWindow(self.root.winfo_id()) / 96 if os.name=="nt" else 1.0
        self.root.title("OFA voice")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.96)
        self.background = "#0a0c10"
        self.transparent = "#010203"
        self.root.configure(bg=self.transparent)
        self.root.attributes("-alpha", 1.0)
        if os.name == "nt": self.root.attributes("-transparentcolor", self.transparent)
        self.width = min(420, int(self.root.winfo_screenwidth()/self.scale)-32)
        width = self.root.winfo_screenwidth()
        self.root.geometry(f"{int(self.width*self.scale)}x{int(294*self.scale)}+{int((width-self.width*self.scale)//2)}+{int(12*self.scale)}")
        self.canvas = tk.Canvas(self.root,width=int(self.width*self.scale),height=int(294*self.scale),bg=self.transparent,highlightthickness=0)
        self.canvas.pack()
        self._rounded(1,1,self.width-1,293,18,self.background,"#292b31")
        self.canvas.create_text(18,29,text="O  F  A",anchor="w",fill="#f4f6f8",font=("Segoe UI",11))
        self.callbacks = {}
        self._button(self.width-30,29,"x","Close voice",lambda:self._action("stop"))
        assets=Path(__file__).with_name("assets")
        meta=json.loads((assets/"orb.json").read_text())
        from fractions import Fraction
        ratio=Fraction(self.scale/2).limit_denominator(8)
        self.frames=[tk.PhotoImage(file=str(assets/"liquid-orb.gif"),format=f"gif -index {i}").zoom(ratio.numerator).subsample(ratio.denominator) for i in range(meta["frames"])]
        self.frame_ms=meta["frame_ms"]
        self.frame_index=0
        self.visible=False
        self.orb=self.canvas.create_image(self.width//2,112,image=self.frames[0])
        self.label=self.canvas.create_text(self.width//2,193,text="How can I help?",width=self.width-32,
                                          fill="#c9d1d9",font=("Segoe UI",11))
        self._rounded(17,215,self.width-117,254,12,"#191b20","#00c8ff")
        self.entry=tk.Entry(self.root,bg="#191b20",fg="#f4f6f8",insertbackground="#f4f6f8",
                            relief="flat",font=("Segoe UI",11))
        self.entry_item=self.canvas.create_window(27,235,window=self.entry,width=self.width-155,height=30,anchor="w")
        self.entry.insert(0,"Ask or talk to your agent...")
        self.entry.bind("<FocusIn>",self._entry_focus)
        self.entry.bind("<Button-1>",lambda _:self._activate_input())
        self.entry.bind("<Return>",self._submit)
        for x,icon,label,action in ((self.width-88,"Mic","Stop microphone","stop"),(self.width-38,"Stop","Interrupt speech","interrupt")):
            self._rounded(x-21,215,x+21,254,12,"#202228","#42444c")
            if action=="stop":
                self.canvas.create_oval(x-3,224,x+3,236,outline="#bfc2d0",width=1.5,tags=(label,))
                self.canvas.create_arc(x-6,228,x+6,240,start=180,extent=180,style="arc",outline="#bfc2d0",width=1.5,tags=(label,))
                self.canvas.create_line(x,240,x,245,fill="#bfc2d0",tags=(label,))
            else:
                self.canvas.create_polygon(x-7,231,x-3,231,x+2,227,x+2,243,x-3,239,x-7,239,fill="#bfc2d0",tags=(label,))
                self.canvas.create_arc(x,227,x+13,243,start=-65,extent=130,style="arc",outline="#8bd5ff",width=1.5,tags=(label,))
            self.canvas.tag_bind(label,"<Button-1>",lambda event,name=action:self._action(name))
        self.canvas.create_text(18,274,text="Caps Lock to close",anchor="w",fill="#8b949e",font=("Segoe UI",8))
        link=self.canvas.create_text(self.width-18,274,text="Open workspace",anchor="e",fill="#8bd5ff",font=("Segoe UI",9))
        self.canvas.tag_bind(link,"<Button-1>",lambda _:webbrowser.open("http://127.0.0.1:3000/desktop"))
        self.root.bind("<Escape>",lambda _:self._action("stop"))
        self.canvas.create_oval(self.width/2-60,52,self.width/2+60,172,outline="#8b949e",width=1)
        self.canvas.scale("all",0,0,self.scale,self.scale)
        self.root.protocol("WM_DELETE_WINDOW", stop)
        self.root.update_idletasks()
        self._nonactivating()
        self.root.withdraw()
        self.root.after(self.frame_ms,self._animate)

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
        set_style(hwnd, -20, get_style(hwnd, -20) | 0x08000000 | 0x80)

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
                self.visible=False
                self.root.withdraw()
                continue
            if not self.visible:
                self._nonactivating()
                self.root.deiconify()
                self.visible=True
            self.canvas.itemconfigure(self.label,text=text or {
                "ARMED":"Getting ready...", "LISTENING":"How can I help? Listening...",
                "THINKING":"Working on your request...", "SPEAKING":"Speaking...",
                "INTERRUPTED":"Listening...", "ERROR":"Voice needs attention",
            }.get(state,state.title()),fill="#ffb357" if state=="ERROR" else "#c9d1d9")
        self.root.after(20, self.pump)

    def run(self) -> None:
        self.pump()
        self.root.mainloop()

    def request_pairing(self, origin, fingerprint, answer):
        self.prompts.put_nowait((origin, fingerprint, answer))

    def request_scope(self, kind, origin, answer):
        self.scope_prompts.put_nowait((kind,origin,answer))

    def _rounded(self,x1,y1,x2,y2,r,fill,outline):
        points=[x1+r,y1,x2-r,y1,x2,y1,x2,y1+r,x2,y2-r,x2,y2,x2-r,y2,x1+r,y2,x1,y2,x1,y2-r,x1,y1+r,x1,y1]
        return self.canvas.create_polygon(points,smooth=True,splinesteps=24,fill=fill,outline=outline)

    def _button(self,x,y,text,label,callback):
        item=self.canvas.create_text(x,y,text=text,fill="#bfc2d0",font=("Segoe UI",12),tags=(label,))
        self.canvas.tag_bind(item,"<Button-1>",lambda _:callback())

    def _animate(self):
        if self.visible:
            self.frame_index=(self.frame_index+1)%len(self.frames)
            self.canvas.itemconfigure(self.orb,image=self.frames[self.frame_index])
        self.root.after(self.frame_ms,self._animate)

    def _action(self,name):
        callback=self.callbacks.get(name)
        if callback: callback()

    def _activate_input(self):
        if os.name=="nt":
            from ctypes import wintypes as wt
            user=ctypes.WinDLL("user32",use_last_error=True)
            user.GetParent.argtypes=[wt.HWND]; user.GetParent.restype=wt.HWND
            get=user.GetWindowLongPtrW; get.argtypes=[wt.HWND,ctypes.c_int]; get.restype=ctypes.c_ssize_t
            put=user.SetWindowLongPtrW; put.argtypes=[wt.HWND,ctypes.c_int,ctypes.c_ssize_t]; put.restype=ctypes.c_ssize_t
            hwnd=user.GetParent(self.root.winfo_id()); put(hwnd,-20,get(hwnd,-20)&~(0x08000000|0x20))
        self.root.focus_force(); self.entry.focus_set()

    def _entry_focus(self,event):
        if self.entry.get()=="Ask or talk to your agent...": self.entry.delete(0,"end")

    def _submit(self,event):
        text=self.entry.get().strip()
        if text and text!="Ask or talk to your agent..." and "send" in self.callbacks:
            self.callbacks["send"](text[:4096]); self.entry.delete(0,"end")
