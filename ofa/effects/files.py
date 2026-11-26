"""Local file effects: search, read, write. Credential files are never read."""
from __future__ import annotations

import fnmatch
import os
import re
import time
from pathlib import Path

from ..memory import Memory
from ..policy import Action
from .scopes import SCOPES


def search_files(memory: Memory, a: Action) -> dict:
    scope = (a.target or "home").casefold()
    root = SCOPES.get(scope) or Path(a.target or "")
    if not root.exists():
        return {"status": "error", "reason": "SCOPE_NOT_FOUND"}
    words = [w for w in re.split(r"\W+", (a.payload or "").casefold()) if w]
    hits, start = [], time.monotonic()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in {"node_modules", "AppData", "$Recycle.Bin"}]
        for f in filenames:
            name = f.casefold()
            if all(w in name for w in words) or (words and fnmatch.fnmatch(name, f"*{'*'.join(words)}*")):
                p = Path(dirpath) / f
                try:
                    st = p.stat()
                except OSError:
                    continue
                hits.append({"name": f, "folder": str(p.parent), "path": str(p), "size": st.st_size,
                             "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime))})
        if len(hits) > 200 or time.monotonic() - start > 8:
            break
    hits.sort(key=lambda x: x["modified"], reverse=True)
    memory.context["last_results"] = [h["path"] for h in hits[:10]]
    return {"count": len(hits), "files": hits[:10], "note": "none found" if not hits else
            ("several match: ask which one" if len(hits) > 1 else "one match")}


def read_file(memory: Memory, path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {"status": "error", "reason": "NOT_A_FILE"}
    if p.suffix.lower() in {".env", ".key", ".pem", ".kdbx", ".dat"} or ".env" in p.name.lower():
        return {"status": "refused", "reason": "SECRET_FILE", "detail": "OFA does not read credential files"}
    data = p.read_bytes()[:8192]
    text = data.decode("utf-8", "replace")
    memory.context["last_file"] = str(p)
    return {"path": str(p), "text": text, "truncated": p.stat().st_size > 8192}


def write_file(memory: Memory, a: Action) -> dict:
    p = Path(a.target or "")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(a.payload or "", encoding="utf-8")
    ok = p.read_text(encoding="utf-8") == (a.payload or "")
    memory.context["last_file"] = str(p)
    return {"written": str(p), "bytes": p.stat().st_size, "verified": ok}
