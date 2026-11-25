"""Load a contender folder: ``<dir>/adapter.py`` -> ``Adapter`` + code hash."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys

EXCLUDE_DIRS = {"__pycache__", ".pytest_cache", "data", "workdir", ".venv",
                ".git", "tmp"}
EXCLUDE_EXT = (".pyc", ".db", ".sqlite", ".sqlite3", "-wal", "-shm")
BENCH_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def code_hash(folder: str) -> str:
    """sha256 over sorted relative paths and bytes of the contender folder."""
    h = hashlib.sha256()
    folder = os.path.abspath(folder)
    files = []
    for root, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDE_DIRS)
        for n in names:
            if not n.endswith(EXCLUDE_EXT):
                files.append(os.path.join(root, n))
    for p in sorted(files, key=lambda p: os.path.relpath(p, folder)):
        rel = os.path.relpath(p, folder).replace(os.sep, "/")
        h.update(rel.encode() + b"\0")
        with open(p, "rb") as f:
            h.update(f.read() + b"\0")
    return h.hexdigest()


def load_adapter_class(folder: str) -> type:
    """Import ``adapter.py`` from ``folder`` under a unique module name."""
    folder = os.path.abspath(folder)
    for p in (BENCH_ROOT, folder):
        if p not in sys.path:
            sys.path.insert(0, p)
    name = "contender_" + hashlib.sha1(folder.encode()).hexdigest()[:10]
    if name in sys.modules:
        return sys.modules[name].Adapter
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(folder, "adapter.py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"no adapter.py in {folder}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.Adapter
