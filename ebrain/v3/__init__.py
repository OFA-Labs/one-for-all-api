"""E-Brain V3 implementation (disabled by default; legacy ``ebrain`` stays intact).

V3 is a versioned, separately activated implementation of the engineering-memory
service described in ``docs/ebrain/SPEC_DEV_BRAIN_V3.md``. Importing this package
has no side effects and does not change schema-1 behaviour.
"""

__all__ = ["contracts", "config", "errors", "clocks"]
