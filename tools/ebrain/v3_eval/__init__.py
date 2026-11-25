"""Importable alias for the hyphenated ``tools/ebrain/v3-eval`` directory.

Python identifiers cannot contain ``-``, so ``v3-eval`` cannot be imported by
name. This small bootstrap loads each module of that directory under the
canonical ``tools.ebrain.v3_eval`` namespace, preserving one source of truth
and working unchanged on Windows. From the API repository root::

    python -m tools.ebrain.v3_eval.cli --help

or, with an explicit path::

    $env:PYTHONPATH = "<repo root>"
    python -c "from tools.ebrain.v3_eval import generator; print(generator.__file__)"

The physical ``cli.py`` in this package is a thin launcher that loads the real
CLI from ``v3-eval`` under a private module name, so ``python -m`` can find it
without a runpy warning or a second copy of the source.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from types import ModuleType

_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
_SOURCE_DIR = os.path.join(os.path.dirname(_PACKAGE_DIR), "v3-eval")
_ALIAS = __name__

_EAGER_MODULES = (
    "schema", "manifest", "generator", "oracle", "metrics", "runner",
)


def _load_module(name: str, alias: str | None = None) -> ModuleType:
    """Load ``v3-eval/<name>.py`` under ``tools.ebrain.v3_eval.<alias>``."""
    full = f"{_ALIAS}.{alias or name}"
    cached = sys.modules.get(full)
    if cached is not None:
        return cached
    path = os.path.join(_SOURCE_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(full, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load v3-eval module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(full, None)
        raise
    return module


for _name in _EAGER_MODULES:
    globals()[_name] = _load_module(_name)

EVAL_PACKAGE_VERSION = "1.0.0"
SOURCE_DIR = _SOURCE_DIR

__all__ = [*_EAGER_MODULES, "cli", "EVAL_PACKAGE_VERSION", "SOURCE_DIR"]
