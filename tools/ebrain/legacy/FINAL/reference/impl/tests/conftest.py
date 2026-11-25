"""Shared by FINAL/reference/impl/tests and one-for-all-api/tests (same file, same layout).

Layout in both places: <ROOT>/ebrain/*.py and <ROOT>/tests/*.py. No benchmark tree is needed.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
STORE_SRC = os.environ.get("EBRAIN_TAGS_SRC", os.path.join(ROOT, "ebrain", "store.py"))


@pytest.fixture
def make_store(tmp_path):
    from ebrain.store import Store
    opened = []

    def make(config=None, user_id="local", path=None):
        s = Store(str(path or tmp_path), config, user_id)
        opened.append(s)
        return s
    yield make
    for s in opened:
        s.close()


@pytest.fixture
def ad(make_store):
    return make_store()
