"""Benchmark-only adapter for the current API Store, never the frozen reference.

The active wrapper records hashes of this file AND product ebrain/*.py files;
the legacy harness's contender-folder hash alone cannot identify product code.
"""
from pathlib import Path
import sys

API_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(API_ROOT))
from ebrain.store import Store  # noqa: E402


class Adapter(Store):
    name = "ebrain-current-product"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")
