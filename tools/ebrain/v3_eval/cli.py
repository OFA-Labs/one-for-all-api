"""Physical launcher for ``python -m tools.ebrain.v3_eval.cli``.

The real implementation lives in the sibling hyphenated directory
``tools/ebrain/v3-eval/cli.py``; this file contains no duplicated logic.
"""
from __future__ import annotations

import sys

from . import _load_module

_impl = _load_module("cli", "_cli_impl")
globals().update({k: v for k, v in vars(_impl).items()
                  if not k.startswith("__")})

if __name__ == "__main__":
    sys.exit(main())
