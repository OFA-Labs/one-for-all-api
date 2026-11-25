"""Ordered commit ledger: Postgres adapter plus an in-memory reference backend.

The in-memory backend implements the same contract for deterministic tests; it
is NOT evidence for Postgres/RLS/concurrency isolation, which needs a real DB.
"""
