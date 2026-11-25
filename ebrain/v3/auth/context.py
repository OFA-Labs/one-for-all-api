"""Server-derived trusted context.

Request bodies never carry org/grants/authority. The development principal
provider is explicitly synthetic and must be unreachable when OIDC is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..config import V3Config
from ..contracts import (
    Action,
    AuthorizedContext,
    Grant,
    Principal,
    SourceContract,
    Snapshot,
)
from ..errors import AuthEpochChanged, Forbidden, Unauthenticated

__all__ = [
    "DevelopmentPrincipalProvider", "authorize", "build_context", "check_read_epoch",
]


@dataclass(frozen=True)
class DevelopmentPrincipalProvider:
    """Synthetic, deterministic identities for isolated tests/development only.

    This is NOT SSO and must never be active in a company build. Tokens are
    opaque test handles supplied by the test harness, never secrets from disk.
    """

    registry: Mapping[str, Principal]
    development_only: bool = True

    def authenticate(self, token: str) -> Principal:
        principal = self.registry.get(token)
        if principal is None:
            raise Unauthenticated("unknown or expired credential")
        return principal


def build_context(
    principal: Principal,
    *,
    request_id: str,
    scope: str,
    source_contract: SourceContract = SourceContract.FIRST_PARTY_DECLARED,
    source_id: str = "",
) -> AuthorizedContext:
    """Derive an AuthorizedContext strictly from server-side principal state."""
    if not principal.org_id or not principal.subject:
        raise Unauthenticated("principal is not bound to an organization")
    grants = tuple(g for g in principal.grants if g.scope in ("*", scope))
    predicates: set[str] = set()
    actions: set[Action] = set()
    for grant in grants:
        predicates.update(grant.predicates)
        actions.update(grant.actions)
    return AuthorizedContext(
        principal=principal,
        request_id=request_id,
        scope=scope,
        allowed_predicates=tuple(sorted(predicates)),
        allowed_actions=tuple(sorted(actions, key=lambda a: a.value)),
        source_contract=source_contract,
        auth_epoch=principal.auth_epoch,
        source_id=source_id,
    )


def authorize(
    ctx: AuthorizedContext,
    *,
    predicate: str,
    action: Action,
    config: V3Config | None = None,
    now_iso: str | None = None,
) -> None:
    """Fail closed on missing/expired/empty grants. No text-based authority."""
    if not ctx.principal.org_id or not ctx.principal.subject:
        raise Unauthenticated("unbound principal")
    if action not in ctx.allowed_actions:
        raise Forbidden(f"action {action.value} is not granted in this scope")
    if not ctx.allows(predicate, action):
        raise Forbidden("predicate is not granted in this scope")
    for grant in ctx.principal.grants:
        if grant.scope not in ("*", ctx.scope):
            continue
        if grant.expires_at and now_iso is not None and grant.expires_at <= now_iso:
            raise Forbidden("grant has expired")


def check_read_epoch(ctx: AuthorizedContext, snapshot: Snapshot) -> None:
    """Final authorization check before delivery, also for historical reads."""
    if snapshot.auth_epoch != ctx.auth_epoch:
        raise AuthEpochChanged("authorization epoch changed during read")
