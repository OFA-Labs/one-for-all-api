"""Traceability: C02."""
from __future__ import annotations

import pytest

from ebrain.v3.contracts import ClaimKind
from ebrain.v3.errors import AmbiguousIdentity
from ebrain.v3.identity.keys import canonical_key, normalize_qualifiers

from .v3_helpers import ORG, SCOPE


def test_C02_scoped_typed_identity():
    common = dict(org_id=ORG, resource_namespace="repo", resource_id="svc",
                  predicate="decision.status",
                  qualifiers={"repo": "acme/api", "environment": "prod"})
    a = canonical_key(**common, scope=SCOPE, kind=ClaimKind.ASSERTION)
    b = canonical_key(
        org_id=ORG, resource_namespace="repo", resource_id="svc", scope=SCOPE,
        predicate="decision.status", kind=ClaimKind.ASSERTION,
        qualifiers={"repo": "acme/api", "environment": "stage"},
    )
    c = canonical_key(**common, scope="proj-b", kind=ClaimKind.ASSERTION)
    d = canonical_key(org_id=ORG, resource_namespace="repo", resource_id="svc",
                      scope=SCOPE, predicate="owner.assignment", kind=ClaimKind.ASSERTION,
                      qualifiers={"repo": "acme/api"})
    e = canonical_key(**common, scope=SCOPE, kind=ClaimKind.OBSERVATION)
    assert len({a.canonical(), b.canonical(), c.canonical(), d.canonical(), e.canonical()}) == 5
    with pytest.raises(AmbiguousIdentity):
        normalize_qualifiers("repo.branch.head.sha", {"repo": "acme/api"})
