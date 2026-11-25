"""Immutable V3 configuration with disabled-by-default activation flags.

Safety properties (hard auth, ingest gate, approvals, evidence eligibility,
current cardinality, audit) are NOT configurable. ``validate()`` refuses any
config that attempts to carry them as flags. Operational knobs are separate
from semantic/version pins.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Mapping

from .contracts import digest_of
from .errors import Malformed


@dataclass(frozen=True)
class V3Config:
    # Activation knobs (all OFF). Production routing requires explicit owner approval.
    v3_enabled: bool = False
    schema3_http_enabled: bool = False
    mcp_enabled: bool = False
    voice_v3_enabled: bool = False
    company_routing_enabled: bool = False
    # Optional accelerators — off by default; model-free resolver is unconditional.
    semantic_filing_enabled: bool = False
    vector_retrieval_enabled: bool = False
    graph_retrieval_enabled: bool = False
    rerank_enabled: bool = False
    nli_maintenance_enabled: bool = False
    oidc_enabled: bool = False
    scim_enabled: bool = False
    # Operational bounds (tunable, not semantic).
    max_text_chars: int = 20_000
    max_bytes: int = 1_048_576
    max_nesting: int = 12
    outbox_max_attempts: int = 5
    job_lease_ticks: int = 16
    query_max_candidates: int = 200
    retrieval_budget_ms: int = 200
    # Version pins (change only through an approved activation manifest).
    policy_version: str = "1"
    identity_generation: int = 1
    model_manifest_id: str = ""
    retrieval_generation: str = ""

    def validate(self) -> V3Config:
        if self.max_text_chars < 1 or self.max_bytes < 1 or self.max_nesting < 1:
            raise Malformed("configuration bounds must be positive")
        if self.outbox_max_attempts < 1 or self.job_lease_ticks < 1:
            raise Malformed("outbox bounds must be positive")
        return self

    def with_overrides(self, overrides: Mapping[str, object]) -> V3Config:
        allowed = {f for f in self.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = set(overrides) - allowed
        if unknown:
            raise Malformed(f"unknown configuration keys: {sorted(unknown)}")
        return replace(self, **overrides).validate()

    def digest(self) -> str:
        return digest_of({"config": self.as_dict()})

    def as_dict(self) -> dict[str, object]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}  # type: ignore[attr-defined]

    @property
    def disabled_summary(self) -> tuple[str, ...]:
        return tuple(
            name for name in (
                "v3_enabled", "schema3_http_enabled", "mcp_enabled", "voice_v3_enabled",
                "company_routing_enabled", "semantic_filing_enabled", "vector_retrieval_enabled",
                "graph_retrieval_enabled", "rerank_enabled", "nli_maintenance_enabled",
                "oidc_enabled", "scim_enabled",
            ) if not getattr(self, name)
        )


DEFAULT_CONFIG: Final = V3Config().validate()

# These security invariants can never be supplied as configuration flags.
FORBIDDEN_CONFIG_KEYS: Final[frozenset[str]] = frozenset({
    "auth_disabled", "bypass_gate", "allow_unauthorized_current", "skip_approval",
    "allow_external_current", "allow_physical_rollback", "disable_audit", "disable_rls",
    "disable_erasure", "allow_multi_current", "accept_raw_payload",
})


def assert_no_safety_override(overrides: Mapping[str, object]) -> None:
    bad = FORBIDDEN_CONFIG_KEYS.intersection(overrides)
    if bad:
        raise Malformed(f"safety invariants are not configurable: {sorted(bad)}")
