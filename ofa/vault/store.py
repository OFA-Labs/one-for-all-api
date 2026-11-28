"""Encrypted vault (§8.3 option 3). AES-256-GCM per value, AAD = handle; data key wrapped by DPAPI
(current user) and unwrapped only after OS user presence. Metadata is non-secret and LLM-visible."""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..egress import EGRESS
from .handles import format_vault, parse_handle
from .unlock import PresenceVerifier


class VaultLocked(RuntimeError):
    pass


class VaultError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def dpapi_wrap(key: bytes) -> bytes:
    from voice.protected_store import _crypt
    return _crypt(key)


def dpapi_unwrap(blob: bytes) -> bytes:
    from voice.protected_store import _crypt
    return _crypt(blob, True)


SCHEMA = """CREATE TABLE IF NOT EXISTS items(handle TEXT PRIMARY KEY, base TEXT, class TEXT, service TEXT,
label TEXT, version INTEGER, nonce BLOB, ct BLOB, meta TEXT, created REAL, last_used REAL, revoked INTEGER DEFAULT 0)"""


class Vault:
    def __init__(self, root: Path, verifier: PresenceVerifier,
                 wrap: Callable[[bytes], bytes] = dpapi_wrap, unwrap: Callable[[bytes], bytes] = dpapi_unwrap,
                 idle_seconds: float = 1800):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.verifier, self._wrap, self._unwrap = verifier, wrap, unwrap
        self.idle_seconds = idle_seconds
        self._key: bytes | None = None
        self._touched = 0.0
        self._lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "vault.db", check_same_thread=False)
        self.db.execute(SCHEMA)
        self.db.commit()

    # --- lock state ------------------------------------------------------------------------
    @property
    def unlocked(self) -> bool:
        if self._key and time.monotonic() - self._touched > self.idle_seconds:
            self.lock()
        return self._key is not None

    def unlock(self, reason: str = "Unlock your OFA vault for this session") -> bool:
        with self._lock:
            if self.unlocked:
                return True
            if not self.verifier.verify(reason):
                return False
            keyfile = self.root / "vault.key"
            if keyfile.exists():
                self._key = self._unwrap(keyfile.read_bytes())
            else:
                key = AESGCM.generate_key(256)
                tmp = keyfile.with_suffix(".partial")
                tmp.write_bytes(self._wrap(key))
                os.replace(tmp, keyfile)
                self._key = key
            self._touched = time.monotonic()
            # Arm leak canaries for every stored secret so a value can never leave via any sink.
            aes = AESGCM(self._key)
            for handle, nonce, ct in self.db.execute(
                    "SELECT handle, nonce, ct FROM items WHERE revoked=0 AND class IN ('D2','D3')").fetchall():
                try:
                    EGRESS.register(aes.decrypt(nonce, ct, handle.encode()).decode(), handle)
                except Exception:
                    pass
            return True

    def lock(self) -> None:
        with self._lock:
            self._key = None

    def _aes(self) -> AESGCM:
        if not self.unlocked:
            raise VaultLocked("Vault is locked")
        self._touched = time.monotonic()
        return AESGCM(self._key)

    # --- items -----------------------------------------------------------------------------
    def put(self, data_class: str, service: str, label: str, value: str, *, allowed_targets: list[str] | None = None,
            ops: list[str] | None = None, description: str = "", expected_account: str = "") -> str:
        with self._lock:
            aes = self._aes()
            base = f"vault:{data_class}/{service.lower()}/{label.lower()}"
            row = self.db.execute("SELECT MAX(version) FROM items WHERE base=?", (base,)).fetchone()
            version = (row[0] or 0) + 1
            handle = format_vault(data_class, service, label, version)
            nonce = secrets.token_bytes(12)
            ct = aes.encrypt(nonce, value.encode(), handle.encode())
            meta = {"allowed_targets": allowed_targets or [], "ops": ops or ["fill-field"], "description": description,
                    "expected_account": expected_account.strip()}
            now = time.time()
            self.db.execute("UPDATE items SET revoked=1 WHERE base=?", (base,))
            self.db.execute("INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?,?,0)",
                            (handle, base, data_class, service.lower(), label.lower(), version, nonce, ct,
                             json.dumps(meta), now, None))
            self.db.commit()
            if data_class in ("D2", "D3"):
                EGRESS.register(value, handle)
            return handle

    def reveal_for_broker(self, handle: str) -> str:
        """Only ofa.vault.broker calls this; the value goes straight into a verified field."""
        h = parse_handle(handle)
        with self._lock:
            aes = self._aes()
            row = self.db.execute("SELECT nonce, ct, revoked FROM items WHERE handle=?", (h.raw,)).fetchone()
            if row is None:
                raise VaultError("UNKNOWN_HANDLE")
            if row[2]:
                raise VaultError("REVOKED")
            try:
                value = aes.decrypt(row[0], row[1], h.raw.encode()).decode()
            except Exception as exc:
                raise VaultError("TAMPERED") from exc
            self.db.execute("UPDATE items SET last_used=? WHERE handle=?", (time.time(), h.raw))
            self.db.commit()
            if h.data_class in ("D2", "D3"):
                EGRESS.register(value, h.raw)
            return value

    def reveal_d0(self, handle: str) -> str:
        h = parse_handle(handle)
        if h.data_class != "D0":
            raise VaultError("NOT_PUBLIC")
        return self.reveal_for_broker(handle)

    def meta(self, handle: str) -> dict:
        row = self.db.execute("SELECT handle,class,service,label,version,meta,created,last_used,revoked FROM items "
                              "WHERE handle=?", (handle,)).fetchone()
        if row is None:
            raise VaultError("UNKNOWN_HANDLE")
        return {"handle": row[0], "class": row[1], "service": row[2], "label": row[3], "version": row[4],
                **json.loads(row[5]), "created": row[6], "last_used": row[7], "revoked": bool(row[8])}

    def list(self, include_revoked: bool = False) -> list[dict]:
        q = "SELECT handle FROM items" + ("" if include_revoked else " WHERE revoked=0") + " ORDER BY service,label"
        return [self.meta(r[0]) for r in self.db.execute(q).fetchall()]

    def find(self, service: str | None = None, label: str | None = None, data_class: str | None = None) -> list[dict]:
        return [m for m in self.list() if (service is None or m["service"] == service.lower())
                and (label is None or m["label"] == label.lower()) and (data_class is None or m["class"] == data_class)]

    def revoke(self, handle: str) -> None:
        self.db.execute("UPDATE items SET revoked=1 WHERE handle=?", (handle,))
        self.db.commit()

    def delete(self, handle: str) -> None:
        self.db.execute("DELETE FROM items WHERE handle=?", (handle,))
        self.db.commit()

    def delete_all(self) -> None:
        self.db.execute("DELETE FROM items")
        self.db.commit()

    def rotate(self, handle: str, new_value: str) -> str:
        m = self.meta(handle)
        return self.put(m["class"], m["service"], m["label"], new_value, allowed_targets=m["allowed_targets"],
                        ops=m["ops"], description=m.get("description", ""),
                        expected_account=m.get("expected_account", ""))

    def set_targets(self, handle: str, targets: list[str]) -> None:
        m = self.meta(handle)
        meta = {"allowed_targets": targets, "ops": m["ops"], "description": m.get("description", ""),
                "expected_account": m.get("expected_account", "")}
        self.db.execute("UPDATE items SET meta=? WHERE handle=?", (json.dumps(meta), handle))
        self.db.commit()

    def export_encrypted(self) -> bytes:
        """Re-encrypted with a fresh export key that is itself DPAPI-wrapped; requires presence."""
        if not self.verifier.verify("Export your OFA vault"):
            raise VaultError("PRESENCE_REQUIRED")
        aes, key = self._aes(), AESGCM.generate_key(256)
        items = []
        for m in self.list():
            value = self.reveal_for_broker(m["handle"])
            nonce = secrets.token_bytes(12)
            items.append({"meta": m, "nonce": nonce.hex(),
                          "ct": AESGCM(key).encrypt(nonce, value.encode(), m["handle"].encode()).hex()})
        del aes
        return json.dumps({"key": self._wrap(key).hex(), "items": items}).encode()
