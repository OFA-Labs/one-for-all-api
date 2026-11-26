"""One live host per interactive Windows session; fake probes stay independent."""
import ctypes
import os
from ctypes import wintypes

_handle=None


def acquire():
    global _handle
    if os.name!='nt': return True
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    kernel.CreateMutexW.restype=wintypes.HANDLE
    handle=kernel.CreateMutexW(None,False,r'Local\OFA-Desktop-Voice-v1')
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error()==183:
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        kernel.CloseHandle(handle)
        return False
    _handle=handle
    return True
