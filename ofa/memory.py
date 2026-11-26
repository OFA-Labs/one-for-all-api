"""Profile (D0), conversational context and learned mappings (§3.3). User can view/edit/delete."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path


class Memory:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS profile(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS mappings(key TEXT PRIMARY KEY, value TEXT, created REAL, uses INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS ledger(task TEXT, idem TEXT PRIMARY KEY, dest TEXT, verb TEXT, status TEXT, ts REAL);
        """)
        self.db.commit()
        self._lock = threading.Lock()
        self.context: dict = {"last_results": [], "last_file": None, "current_app": None, "pending": None}

    # profile (D0 only; D1+ lives in the vault)
    def get(self, key: str, default=None):
        row = self.db.execute("SELECT value FROM profile WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key: str, value) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO profile VALUES(?,?)", (key, json.dumps(value)))
            self.db.commit()

    def profile(self) -> dict:
        return {k: json.loads(v) for k, v in self.db.execute("SELECT key, value FROM profile")}

    # learned mappings ("my manager" → a contact label)
    def remember(self, key: str, value: str) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO mappings(key,value,created) VALUES(?,?,?)",
                            (key.casefold().strip(), value.strip(), time.time()))
            self.db.commit()

    def mappings(self) -> dict:
        return {k: v for k, v in self.db.execute("SELECT key, value FROM mappings ORDER BY key")}

    def forget(self, key: str) -> bool:
        with self._lock:
            n = self.db.execute("DELETE FROM mappings WHERE key=?", (key.casefold().strip(),)).rowcount
            self.db.commit()
            return bool(n)

    def delete_all(self) -> None:
        with self._lock:
            self.db.executescript("DELETE FROM profile; DELETE FROM mappings; DELETE FROM ledger;")
            self.db.commit()
        self.context = {"last_results": [], "last_file": None, "current_app": None, "pending": None}

    # references (§3.3)
    ORDINALS = {"first": 0, "1st": 0, "pehla": 0, "pehli": 0, "second": 1, "2nd": 1, "doosra": 1, "dusra": 1,
                "doosri": 1, "third": 2, "3rd": 2, "teesra": 2, "teesri": 2, "last": -1, "aakhri": -1}

    def resolve(self, ref: str) -> dict:
        r = ref.casefold()
        results = self.context.get("last_results") or []
        for word, idx in self.ORDINALS.items():
            if word in r.split() and results:
                try:
                    return {"resolved": results[idx]}
                except IndexError:
                    return {"ambiguous": True, "reason": f"there are only {len(results)} results"}
        if any(w in r.split() for w in ("this", "that", "it", "isko", "usko", "wahi", "ye", "woh", "same")):
            if len(results) == 1:
                return {"resolved": results[0]}
            if self.context.get("last_file") and any(w in r for w in ("file", "document", "doc")):
                return {"resolved": self.context["last_file"]}
            if len(results) > 1:
                return {"ambiguous": True, "options": results[:5]}
        for key, value in self.mappings().items():
            if key in r:
                self.db.execute("UPDATE mappings SET uses=uses+1 WHERE key=?", (key,))
                return {"resolved": value, "via": f"remembered '{key}'"}
        return {"unresolved": True}

    # idempotency ledger for outbound effects (C9)
    def ledger_get(self, idem: str) -> str | None:
        row = self.db.execute("SELECT status FROM ledger WHERE idem=?", (idem,)).fetchone()
        return row[0] if row else None

    def ledger_set(self, task: str, idem: str, dest: str, verb: str, status: str) -> None:
        with self._lock:
            self.db.execute("INSERT OR REPLACE INTO ledger VALUES(?,?,?,?,?,?)", (task, idem, dest, verb, status, time.time()))
            self.db.commit()

    def ledger(self, task: str) -> list[dict]:
        return [{"dest": d, "verb": v, "status": s} for d, v, s in
                self.db.execute("SELECT dest, verb, status FROM ledger WHERE task=? ORDER BY ts", (task,))]
