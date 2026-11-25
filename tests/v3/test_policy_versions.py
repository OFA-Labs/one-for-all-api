"""Traceability: M08."""
from __future__ import annotations

import pytest

from ebrain.v3.errors import Malformed
from ebrain.v3.resolver.policy import PolicyVersion


def test_M08_approved_versioned_activation():
    manifest = {
        "version": "2", "effective_seq": 7,
        "required_authority": {"decision.status": "human"},
        "allow_unknown_valid_time": False,
    }
    policy = PolicyVersion.from_manifest(manifest)
    assert policy.effective_seq == 7
    assert policy.digest() == policy.digest()
    with pytest.raises(Malformed):
        PolicyVersion.from_manifest({**manifest, "disable_grants": True})
