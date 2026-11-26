"""Desktop harness (plan 07). Windows backend in win.py; fake backend for tests."""
from .api import Harness, HarnessError

__all__ = ["Harness", "HarnessError"]
