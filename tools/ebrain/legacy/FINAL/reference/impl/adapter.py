"""Benchmark-harness glue only (not shipped to one-for-all-api): Adapter = Store for one user.

The harness puts this folder on sys.path, so ``ebrain`` resolves to ./ebrain.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ebrain.store import Store  # noqa: E402


class Adapter(Store):
    name = "ebrain-reference"

    def __init__(self, workdir, config=None):
        super().__init__(workdir, config, user_id="local")
