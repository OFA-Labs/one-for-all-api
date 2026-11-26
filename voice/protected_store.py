"""Windows current-user DPAPI storage. Never persist an unencrypted pairing secret."""
from __future__ import annotations

import ctypes
import json
import os
from ctypes import wintypes as wt
from pathlib import Path


def _crypt(data: bytes, decrypt: bool = False) -> bytes:
    if os.name != "nt":
        raise OSError("Persistent pairing requires Windows DPAPI")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wt.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    source_buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, result = Blob(len(data), source_buffer), Blob()
    api = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [wt.HLOCAL]
    operation = api.CryptUnprotectData if decrypt else api.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wt.DWORD, ctypes.POINTER(Blob)]
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(result)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(result.data, result.size)
    finally:
        kernel.LocalFree(result.data)


class ProtectedStore:
    def __init__(self, path: Path):
        self.path = path

    def read(self) -> dict:
        if not self.path.exists():
            return {}
        if self.path.stat().st_size > 262144:
            raise ValueError("Pairing profile exceeds its bound")
        return json.loads(_crypt(self.path.read_bytes(), True))

    def write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".partial")
        temporary.write_bytes(_crypt(json.dumps(data).encode()))
        os.replace(temporary, self.path)
