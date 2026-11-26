"""Bearer-token principals for History (development seam, not production auth).

``HISTORY_TOKENS`` maps tokens to ``member`` (one user, read-only) or ``service`` (the future
task engine, writes for an explicit user). Unset or invalid configuration fails closed: every
request is 401. A member's user id comes only from the token, never from a request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

from fastapi import Depends, Header

from .errors import HistoryError


@dataclass(frozen=True)
class Principal:
    user_id: str | None
    role: Literal["member", "service"]


def make_guards(tokens: dict) -> tuple[Callable[..., Principal], Callable[..., Principal]]:
    def principal(authorization: str | None = Header(default=None)) -> Principal:
        scheme, _, token = (authorization or "").partition(" ")
        entry = tokens.get(token.strip()) if scheme.lower() == "bearer" and token.strip() else None
        if not isinstance(entry, dict):
            raise HistoryError(401, "unauthorized", "Missing or unknown bearer token.")
        return Principal(entry.get("user"), entry["role"])

    def member(p: Principal = Depends(principal)) -> Principal:
        if p.role != "member" or not p.user_id:
            raise HistoryError(403, "forbidden", "A member token is required.")
        return p

    def service(p: Principal = Depends(principal)) -> Principal:
        if p.role != "service":
            raise HistoryError(403, "forbidden", "A service token is required.")
        return p

    return member, service
