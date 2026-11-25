"""OIDC/SCIM seams (M13 CP13.1). Disabled unless explicitly configured.

No provider is selected here and no live provider is contacted. An injected
verifier must validate issuer, audience, signature, expiry and organization
membership before a principal can exist. Role/email/localStorage is never proof.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..config import V3Config
from ..contracts import Principal
from ..errors import Forbidden, Unauthenticated


class TokenVerifier(Protocol):
    def verify(self, token: str) -> dict[str, object]: ...


@dataclass(frozen=True)
class OidcConfig:
    issuer: str
    audience: str
    org_claim: str = "org_id"
    subject_claim: str = "sub"

    def validate_claims(self, claims: dict[str, object]) -> str:
        if not self.issuer or not self.audience:
            raise Unauthenticated("OIDC issuer/audience not configured")
        if claims.get("iss") != self.issuer:
            raise Unauthenticated("issuer mismatch")
        audience = claims.get("aud")
        if isinstance(audience, str):
            audiences = {audience}
        elif isinstance(audience, (list, tuple)):
            audiences = set(audience)
        else:
            audiences = set()
        if self.audience not in audiences:
            raise Unauthenticated("audience mismatch")
        org = claims.get(self.org_claim)
        if not isinstance(org, str) or not org:
            raise Forbidden("no organization membership claim")
        return org


@dataclass
class OidcProvider:
    cfg: V3Config
    oidc: OidcConfig
    verifier: TokenVerifier
    directory: "ScimDirectory"

    def authenticate(self, token: str) -> Principal:
        if not self.cfg.oidc_enabled:
            raise Unauthenticated("OIDC is disabled")
        claims = self.verifier.verify(token)
        org = self.oidc.validate_claims(claims)
        subject = str(claims.get(self.oidc.subject_claim, ""))
        if not subject:
            raise Unauthenticated("missing subject")
        principal = self.directory.lookup(org, subject)
        if principal is None:
            raise Forbidden("subject is not provisioned for this organization")
        if principal.auth_epoch != int(claims.get("auth_epoch", principal.auth_epoch)):
            raise Unauthenticated("stale authentication epoch")
        return principal


@dataclass
class ScimDirectory:
    """Test-owned provisioning fixtures; revocation is immediate and auditable."""

    principals: dict[tuple[str, str], Principal] = field(default_factory=dict)
    revocations: set[tuple[str, str]] = field(default_factory=set)

    def provision(self, principal: Principal) -> None:
        key = (principal.org_id, principal.subject)
        if key in self.revocations:
            self.revocations.discard(key)
        self.principals[key] = principal

    def revoke(self, org_id: str, subject: str) -> None:
        key = (org_id, subject)
        self.revocations.add(key)
        self.principals.pop(key, None)

    def lookup(self, org_id: str, subject: str) -> Principal | None:
        key = (org_id, subject)
        if key in self.revocations:
            return None
        return self.principals.get(key)
