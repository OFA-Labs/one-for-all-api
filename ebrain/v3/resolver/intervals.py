"""Half-open UTC interval helpers (M11 CP11.4). Strings compare lexicographically
for canonical ISO-8601 UTC timestamps; unknown times are explicit, never inferred.
"""
from __future__ import annotations

from ..contracts import Claim


def includes(claim: Claim, valid_at: str, *, allow_unknown: bool = False) -> bool:
    if claim.valid_from is None:
        return allow_unknown
    if claim.valid_from > valid_at:
        return False
    if claim.valid_to is not None and claim.valid_to <= valid_at:
        return False
    return True


def is_future(claim: Claim, valid_at: str) -> bool:
    return claim.valid_from is not None and claim.valid_from > valid_at


def is_expired(claim: Claim, valid_at: str) -> bool:
    return claim.valid_to is not None and claim.valid_to <= valid_at


def overlaps(a: Claim, b: Claim) -> bool:
    """Overlap on effective intervals; unknown intervals never overlap implicitly."""
    if a.valid_from is None or b.valid_from is None:
        return False
    start = max(a.valid_from, b.valid_from)
    end_a = a.valid_to or "\uffff"
    end_b = b.valid_to or "\uffff"
    return start < min(end_a, end_b)


def freshness(claim: Claim, valid_at: str, now: str) -> str:
    if is_expired(claim, valid_at):
        return "expired"
    if is_future(claim, valid_at):
        return "unknown"
    if claim.valid_to is not None and claim.valid_to <= now:
        return "stale"
    return "fresh"
