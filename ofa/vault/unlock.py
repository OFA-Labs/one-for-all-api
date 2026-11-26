"""OS user presence for vault unlock (§8.3): Windows Hello, else Windows credential prompt.
Never voice. Tests inject a fake verifier."""
from __future__ import annotations

import asyncio
import ctypes
import os
from ctypes import wintypes as wt
from typing import Protocol


class PresenceVerifier(Protocol):
    def verify(self, reason: str) -> bool: ...


class HelloVerifier:
    def available(self) -> bool:
        try:
            from winrt.windows.security.credentials.ui import UserConsentVerifier, UserConsentVerifierAvailability
            result = asyncio.run(UserConsentVerifier.check_availability_async())
            return result == UserConsentVerifierAvailability.AVAILABLE
        except Exception:
            return False

    def verify(self, reason: str) -> bool:
        from winrt.windows.security.credentials.ui import UserConsentVerifier, UserConsentVerificationResult
        result = asyncio.run(UserConsentVerifier.request_verification_async(reason))
        return result == UserConsentVerificationResult.VERIFIED


class CredUIVerifier:
    """Windows' own secure credential dialog for the current user; OFA verifies with LogonUser and
    discards the buffer. The password never reaches logs, engine or speech."""

    def verify(self, reason: str) -> bool:
        if os.name != "nt":
            return False
        credui = ctypes.WinDLL("credui")
        advapi = ctypes.WinDLL("advapi32")
        ole = ctypes.WinDLL("ole32")

        class Info(ctypes.Structure):
            _fields_ = [("cbSize", wt.DWORD), ("hwndParent", wt.HWND), ("pszMessageText", wt.LPCWSTR),
                        ("pszCaptionText", wt.LPCWSTR), ("hbmBanner", wt.HANDLE)]
        info = Info(ctypes.sizeof(Info), None, reason, "OFA vault unlock", None)
        package, out_buf, out_size, save = wt.ULONG(0), ctypes.c_void_p(), wt.ULONG(0), wt.BOOL(False)
        rc = credui.CredUIPromptForWindowsCredentialsW(ctypes.byref(info), 0, ctypes.byref(package), None, 0,
                                                       ctypes.byref(out_buf), ctypes.byref(out_size),
                                                       ctypes.byref(save), 0x200)  # ENUMERATE_CURRENT_USER
        if rc != 0:
            return False
        try:
            user, dom, pw = (ctypes.create_unicode_buffer(256) for _ in range(3))
            nu, nd, np_ = wt.DWORD(256), wt.DWORD(256), wt.DWORD(256)
            if not credui.CredUnPackAuthenticationBufferW(0, out_buf, out_size, user, ctypes.byref(nu), dom,
                                                          ctypes.byref(nd), pw, ctypes.byref(np_)):
                return False
            name = user.value.split("\\")[-1]
            domain = user.value.split("\\")[0] if "\\" in user.value else "."
            token = wt.HANDLE()
            ok = bool(advapi.LogonUserW(name, domain, pw.value, 2, 0, ctypes.byref(token)))
            if ok:
                ctypes.WinDLL("kernel32").CloseHandle(token)
            ctypes.memset(pw, 0, ctypes.sizeof(pw))
            return ok
        finally:
            ctypes.memset(out_buf, 0, out_size.value)
            ole.CoTaskMemFree(out_buf)


class AutoVerifier:
    def __init__(self) -> None:
        self.hello = HelloVerifier()

    def verify(self, reason: str) -> bool:
        if self.hello.available():
            return self.hello.verify(reason)
        return CredUIVerifier().verify(reason)
