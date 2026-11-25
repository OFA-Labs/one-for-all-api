"""Shared synthetic fixtures for V3 tests (no real data, no secrets)."""
from __future__ import annotations

from ebrain.v3.auth.context import build_context
from ebrain.v3.clocks import FakeClock
from ebrain.v3.contracts import (
    Action,
    ClaimKind,
    Grant,
    Principal,
    SourceContract,
    WriteRequest,
)
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.identity.keys import canonical_key
from ebrain.v3.resolver.policy import DEFAULT_POLICY

ORG = "org-demo"
SCOPE = "proj-a"
OTHER_SCOPE = "proj-b"


def principal(subject: str = "alice", authority: str = "human", scope: str = SCOPE,
              predicates: tuple[str, ...] | None = None, epoch: int = 1) -> Principal:
    return Principal(
        subject=subject, org_id=ORG,
        grants=(Grant(
            scope=scope,
            predicates=predicates or ("decision.status", "repo.branch.head.sha",
                                      "service.config.value", "endpoint.response.code",
                                      "incident.status", "owner.assignment"),
            actions=tuple(Action), authority=authority,  # type: ignore[arg-type]
        ),),
        auth_epoch=epoch,
    )


def ctx(subject: str = "alice", scope: str = SCOPE, authority: str = "human", epoch: int = 1):
    return build_context(
        principal(subject, authority, SCOPE if scope == SCOPE else scope, epoch=epoch),
        request_id=f"req-{subject}", scope=scope,
    )


def key(predicate: str = "decision.status", resource_id: str = "svc",
        scope: str = SCOPE, qualifiers: dict[str, str] | None = None,
        kind: ClaimKind = ClaimKind.ASSERTION):
    return canonical_key(
        org_id=ORG, scope=scope, resource_namespace="repo", resource_id=resource_id,
        predicate=predicate, kind=kind,
        qualifiers=qualifiers or {"repo": "acme/api", "environment": "prod"},
    )


def write(op_id: str, k, value: object, *, idem: str | None = None,
          head: str | None = None, contract: SourceContract = SourceContract.FIRST_PARTY_DECLARED,
          valid_from: str | None = None, observed_seq: int = 0) -> WriteRequest:
    return WriteRequest(
        op_id=op_id, key=k, value=value, source_id="synthetic-git",
        source_revision=f"rev-{op_id}", idempotency_key=idem or op_id,
        expected_head=head, source_contract=contract,
        valid_from=valid_from, observed_seq=observed_seq,
    )


def ledger() -> MemoryLedger:
    return MemoryLedger(org_id=ORG, clock=FakeClock())
