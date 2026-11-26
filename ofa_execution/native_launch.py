"""Operator-configured Windows launch targets and independent packaged identity."""
from __future__ import annotations

import ctypes
import os
import subprocess
import time
from uuid import uuid4
from ctypes import wintypes as wt


def application_identity(pid: int) -> str | None:
    if os.name != "nt":
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    kernel.OpenProcess.restype = wt.HANDLE
    kernel.CloseHandle.argtypes = [wt.HANDLE]
    kernel.GetApplicationUserModelId.argtypes = [wt.HANDLE, ctypes.POINTER(wt.UINT), wt.LPWSTR]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        size = wt.UINT(0)
        if kernel.GetApplicationUserModelId(handle, ctypes.byref(size), None) != 122:
            return None
        name = ctypes.create_unicode_buffer(size.value)
        return name.value if kernel.GetApplicationUserModelId(handle, ctypes.byref(size), name) == 0 else None
    finally:
        kernel.CloseHandle(handle)


def launch(app):
    if app.launch_kind == "interactive_command":
        title = "OFA Claude Code " + uuid4().hex[:12]
        # Every element is native discovery/operator configuration. No shell,
        # model prompt or transcript is passed to the terminal host.
        process = subprocess.Popen([app.console_host, "-w", "new", "new-tab",
            "--title", title, "--suppressApplicationTitle", app.executable], shell=False,
            cwd=app.working_directory or str(__import__('pathlib').Path.home()))
        process.ofa_console_title = title
        process.ofa_started = int((time.time()+11644473600)*10000000)-10000000
        return process
    if app.launch_kind == "aumid":
        import comtypes
        import comtypes.client
        from comtypes import COMMETHOD, GUID, HRESULT, IUnknown

        class ActivationManager(IUnknown):
            _iid_ = GUID("{2E941141-7F97-4756-BA1D-9DECDE894A3D}")
            _methods_ = [COMMETHOD([], HRESULT, "ActivateApplication",
                (["in"], wt.LPCWSTR, "appUserModelId"),
                (["in"], wt.LPCWSTR, "arguments"),
                (["in"], wt.DWORD, "options"),
                (["out"], ctypes.POINTER(wt.DWORD), "processId"))]

        comtypes.CoInitialize()
        manager = comtypes.client.CreateObject(
            "{45BA127D-10A8-46EA-8AB7-56EA9078943C}", interface=ActivationManager)
        manager.ActivateApplication(app.launch_identity, "", 0)
        return None
    if app.launch_kind == "shortcut":
        os.startfile(app.launch_identity)
        return None
    return subprocess.Popen([app.executable, *app.arguments], shell=False,
                            cwd=app.working_directory or None)


def process_parents() -> dict[int, int]:
    if os.name != "nt": return {}
    class Entry(ctypes.Structure):
        _fields_ = [("size",wt.DWORD),("usage",wt.DWORD),("pid",wt.DWORD),
            ("heap",ctypes.c_size_t),("module",wt.DWORD),("threads",wt.DWORD),
            ("parent",wt.DWORD),("priority",ctypes.c_long),("flags",wt.DWORD),("exe",wt.WCHAR*260)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes=[wt.DWORD,wt.DWORD]
    kernel.CreateToolhelp32Snapshot.restype=wt.HANDLE
    kernel.Process32FirstW.argtypes=[wt.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wt.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wt.HANDLE]
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    if snapshot == ctypes.c_void_p(-1).value: return {}
    result={}; entry=Entry(); entry.size=ctypes.sizeof(Entry)
    try:
        ok=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while ok:
            result[entry.pid]=entry.parent
            ok=kernel.Process32NextW(snapshot,ctypes.byref(entry))
        return result
    finally: kernel.CloseHandle(snapshot)


def descendants(pid: int, parents: dict[int,int]) -> set[int]:
    found={pid}
    while True:
        new=found | {child for child,parent in parents.items() if parent in found}
        if new==found: return found-{pid}
        found=new
