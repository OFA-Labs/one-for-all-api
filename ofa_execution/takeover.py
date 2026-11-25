"""Target-window input activity pauses OFA; no key text/activity log is kept."""
import ctypes
import os
import threading
from ctypes import wintypes as wt


class KeyboardEvent(ctypes.Structure):
    _fields_=[('key',wt.DWORD),('scan',wt.DWORD),('flags',wt.DWORD),('time',wt.DWORD),('extra',ctypes.c_size_t)]


class MouseEvent(ctypes.Structure):
    _fields_=[('point',wt.POINT),('data',wt.DWORD),('flags',wt.DWORD),('time',wt.DWORD),('extra',ctypes.c_size_t)]


class TakeoverMonitor:
    def __init__(self, target_window, pause):
        self.target_window,self.pause=target_window,pause
        self.available=False
        self.thread_id=None
        self.ready=threading.Event()

    def start(self):
        if os.name!='nt':return self
        def run():
            user,kernel=ctypes.windll.user32,ctypes.windll.kernel32
            callback=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,ctypes.c_int,wt.WPARAM,wt.LPARAM)
            user.SetWindowsHookExW.argtypes=[ctypes.c_int,callback,wt.HINSTANCE,wt.DWORD]
            user.SetWindowsHookExW.restype=wt.HANDLE
            user.CallNextHookEx.argtypes=[wt.HANDLE,ctypes.c_int,wt.WPARAM,wt.LPARAM]
            user.CallNextHookEx.restype=ctypes.c_ssize_t
            user.GetForegroundWindow.restype=wt.HWND
            kernel.GetModuleHandleW.restype=wt.HMODULE
            self.thread_id=kernel.GetCurrentThreadId()
            def handle(code,msg,pointer,kind):
                if code>=0 and msg in {0x0100,0x0104,0x0201,0x0204,0x020A}:
                    event=ctypes.cast(pointer,ctypes.POINTER(kind)).contents
                    target=self.target_window()
                    if target and user.GetForegroundWindow()==target and event.extra!=0x4F4641:
                        self.pause()
                return user.CallNextHookEx(None,code,msg,pointer)
            key=callback(lambda c,m,p:handle(c,m,p,KeyboardEvent))
            mouse=callback(lambda c,m,p:handle(c,m,p,MouseEvent))
            hooks=[user.SetWindowsHookExW(13,key,kernel.GetModuleHandleW(None),0),
                   user.SetWindowsHookExW(14,mouse,kernel.GetModuleHandleW(None),0)]
            self.available=all(hooks);self.ready.set()
            try:
                if self.available:
                    message=wt.MSG()
                    while user.GetMessageW(ctypes.byref(message),None,0,0)>0:pass
            finally:
                user.UnhookWindowsHookEx.argtypes=[wt.HANDLE]
                for hook in hooks:
                    if hook:user.UnhookWindowsHookEx(hook)
        threading.Thread(target=run,name='ofa-target-takeover',daemon=True).start()
        self.ready.wait(2)
        return self

    def close(self):
        if self.thread_id:
            ctypes.windll.user32.PostThreadMessageW(self.thread_id,0x0012,0,0)
