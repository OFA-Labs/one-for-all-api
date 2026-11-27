"""OFA tests need Windows and requirements-ofa.txt; other jobs (Linux E-Brain CI) skip collecting them."""
import importlib.util
import os
import sys

import pytest

_DEPENDENCIES = ("rapidfuzz", "comtypes", "indic_transliteration", "websockets", "cryptography")
if sys.platform != "win32" or any(importlib.util.find_spec(name) is None for name in _DEPENDENCIES):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path_factory, monkeypatch):
    """No test may read or write the real vault, corpus or memory."""
    monkeypatch.setenv("OFA_DATA_DIR", str(tmp_path_factory.mktemp("ofa-data")))


def pytest_configure(config):
    config.addinivalue_line("markers", "windows: real Windows desktop test (launches only its own disposable windows)")
    config.addinivalue_line("markers", "live: calls a live provider; opt in with OFA_LIVE=1")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "windows" in item.keywords and (os.name != "nt" or os.getenv("OFA_WINDOWS_TESTS") != "1"):
            item.add_marker(pytest.mark.skip(reason="set OFA_WINDOWS_TESTS=1 to drive the real desktop"))
        if "live" in item.keywords and os.getenv("OFA_LIVE") != "1":
            item.add_marker(pytest.mark.skip(reason="set OFA_LIVE=1 for live provider calls"))
