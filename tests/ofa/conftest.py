"""OFA tests need Windows and requirements-ofa.txt; other jobs (Linux E-Brain CI) skip collecting them."""
import importlib.util
import os
import sys

_DEPENDENCIES = ("rapidfuzz", "comtypes", "indic_transliteration", "websockets", "cryptography")
if sys.platform != "win32" or any(importlib.util.find_spec(name) is None for name in _DEPENDENCIES):
    collect_ignore_glob = ["test_*.py"]
