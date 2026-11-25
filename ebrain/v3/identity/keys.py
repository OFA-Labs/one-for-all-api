"""Typed canonical keys and the predicate registry (M9 CP9.1 / C02).

Required qualifiers are NEVER defaulted. Units normalize deterministically.
Repo/branch/token/environment values are exact, never stemmed or case-folded.
Unsupported multi-valued predicates are rejected explicitly rather than flattened.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Mapping

from ..contracts import ClaimKind, FactKey, SourceContract
from ..errors import AmbiguousIdentity, SemanticReject, UnsupportedPredicate

FORBIDDEN_KEY_CHARS: Final = frozenset("|&=:")


@dataclass(frozen=True)
class PredicateSpec:
    predicate: str
    required_qualifiers: tuple[str, ...]
    value_type: str = "scalar"
    unit: str | None = None
    accepted_sources: tuple[SourceContract, ...] = (
        SourceContract.FIRST_PARTY_DECLARED, SourceContract.APPROVED_ARTIFACT,
    )
    multi_valued: bool = False
    freshness_seconds: int | None = None
    writable: bool = True


def _spec(
    predicate: str,
    qualifiers: tuple[str, ...] = (),
    **kwargs: object,
) -> PredicateSpec:
    return PredicateSpec(predicate, qualifiers, **kwargs)  # type: ignore[arg-type]


PREDICATES: Final[Mapping[str, PredicateSpec]] = {
    s.predicate: s for s in (
        _spec("repo.branch.head.sha", ("repo", "branch", "environment")),
        _spec("service.config.value", ("repo", "environment"), unit=None),
        _spec("endpoint.response.code", ("repo", "environment", "endpoint")),
        _spec("incident.status", ("repo", "environment"), value_type="enum"),
        _spec("decision.status", ("repo",), value_type="enum",
              accepted_sources=(SourceContract.FIRST_PARTY_DECLARED,
                                SourceContract.APPROVED_ARTIFACT)),
        _spec("dependency.version", ("repo", "environment", "package")),
        _spec("owner.assignment", ("repo",), value_type="enum"),
        # Explicitly unsupported until a reviewed V3 schema adds it.
        _spec("unsupported.multi_value", ("repo",), multi_valued=True, writable=False),
    )
}


def validate_qualifier(name: str, value: str) -> str:
    if not value or any(c in FORBIDDEN_KEY_CHARS for c in value):
        raise SemanticReject(f"invalid qualifier value for {name}")
    return value


def normalize_qualifiers(
    predicate: str, qualifiers: Mapping[str, str]
) -> tuple[tuple[str, str], ...]:
    """Return exact sorted qualifier pairs or fail when a required one is absent."""
    spec = PREDICATES.get(predicate)
    if spec is None:
        raise UnsupportedPredicate(f"predicate is not registered: {predicate}")
    clean = {k: validate_qualifier(k, str(v)) for k, v in qualifiers.items()}
    missing = [q for q in spec.required_qualifiers if q not in clean]
    if missing:
        raise AmbiguousIdentity(f"missing required qualifiers: {missing}")
    return tuple(sorted(clean.items()))


def canonical_key(
    *,
    org_id: str,
    scope: str,
    resource_namespace: str,
    resource_id: str,
    predicate: str,
    kind: ClaimKind,
    qualifiers: Mapping[str, str],
) -> FactKey:
    spec = PREDICATES.get(predicate)
    if spec is None:
        raise UnsupportedPredicate(f"predicate is not registered: {predicate}")
    if not spec.writable:
        raise UnsupportedPredicate(f"multi-valued predicate is not supported: {predicate}")
    if not resource_id:
        raise AmbiguousIdentity("stable resource id is required")
    return FactKey(
        org_id=org_id,
        scope=scope,
        resource_namespace=resource_namespace,
        resource_id=resource_id,
        predicate=predicate,
        kind=kind,
        qualifiers=normalize_qualifiers(predicate, qualifiers),
    )


def normalize_unit(value: object, unit: str | None) -> tuple[object, str | None]:
    """Deterministic exact unit normalization (no float reformatting or inference)."""
    if unit is None:
        return value, None
    mapping = {"bytes": "B", "byte": "B", "seconds": "s", "second": "s"}
    return value, mapping.get(unit.lower(), unit)
