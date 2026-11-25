"""Immutable, versioned resolver policy and activation manifests (M11 CP11.7/M08)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ..contracts import AUTHORITY_RANK, digest_of
from ..errors import Malformed

UNSAFE_POLICY_KEYS = frozenset({
    "allow_external_current", "allow_multi_current", "skip_approval",
    "allow_derived_current", "disable_audit", "disable_grants",
    "allow_lower_authority_override", "allow_unauthorized_current",
})


@dataclass(frozen=True)
class PolicyVersion:
    version: str
    effective_seq: int
    required_authority: Mapping[str, str]
    allow_unknown_valid_time: bool = False
    activation_digest: str = ""
    history_note: str = ""

    def __post_init__(self) -> None:
        if not self.version or self.effective_seq < 0:
            raise Malformed("policy version requires version and effective_seq")
        for predicate, authority in self.required_authority.items():
            if authority not in AUTHORITY_RANK:
                raise Malformed(f"unknown authority for {predicate}")

    def required_rank(self, predicate: str) -> int:
        return AUTHORITY_RANK[self.required_authority.get(predicate, "agent")]

    def digest(self) -> str:
        return digest_of({
            "version": self.version,
            "effective_seq": self.effective_seq,
            "required_authority": dict(sorted(self.required_authority.items())),
            "allow_unknown_valid_time": self.allow_unknown_valid_time,
        })

    @staticmethod
    def from_manifest(manifest: Mapping[str, object]) -> PolicyVersion:
        """Refuse unsafe config; semantic flags never bypass safety."""
        bad = UNSAFE_POLICY_KEYS.intersection(manifest)
        if bad:
            raise Malformed(f"unsafe policy keys refused: {sorted(bad)}")
        return PolicyVersion(
            version=str(manifest["version"]),
            effective_seq=int(manifest["effective_seq"]),
            required_authority=dict(manifest.get("required_authority", {})),  # type: ignore[arg-type]
            allow_unknown_valid_time=bool(manifest.get("allow_unknown_valid_time", False)),
            activation_digest=digest_of(dict(manifest)),
        )


DEFAULT_POLICY: PolicyVersion = PolicyVersion(
    version="1", effective_seq=0,
    required_authority={"decision.status": "human", "owner.assignment": "human"},
    activation_digest="",
)
