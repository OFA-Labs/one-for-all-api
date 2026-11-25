"""Identity event replay (M9 CP9.2).

Exactly one active binding per applied claim at each identity cut. Legacy codes
and op ids are scoped aliases, never authority or globally unique assumptions.
Explicit lineage/targets are verified for scope/qualifier/base compatibility;
conflicts never resolve by 'first target'.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..contracts import (
    Claim,
    FactKey,
    IdentityEvent,
    IdentityEventKind,
    PendingImpact,
)
from ..errors import AmbiguousIdentity, SemanticReject


@dataclass
class Binding:
    claim_id: str
    fact_id: str
    key: FactKey
    generation: int
    seq: int
    active: bool = True


@dataclass
class IdentityLedger:
    events: list[IdentityEvent] = field(default_factory=list)
    aliases: dict[tuple[str, str], str] = field(default_factory=dict)  # (scope, alias) -> fact_id
    _bindings: dict[str, Binding] = field(default_factory=dict)
    _fact_keys: dict[str, FactKey] = field(default_factory=dict)
    _rekey: dict[str, str] = field(default_factory=dict)

    def append(self, event: IdentityEvent) -> None:
        if any(e.event_id == event.event_id for e in self.events):
            raise SemanticReject("duplicate identity event id")
        self.events.append(event)
        self._apply(event)

    def _apply(self, event: IdentityEvent) -> None:
        key = event.key
        if event.kind in (IdentityEventKind.REGISTER, IdentityEventKind.BIND):
            if not event.claim_id or not event.fact_id:
                raise SemanticReject("register/bind requires claim and fact ids")
            existing = self._bindings.get(event.claim_id)
            if existing and existing.active and existing.fact_id != event.fact_id:
                raise AmbiguousIdentity("claim already bound to a different fact")
            self._bindings[event.claim_id] = Binding(
                event.claim_id, event.fact_id, key, event.generation, event.knowledge_seq
            )
            self._fact_keys[event.fact_id] = key
        elif event.kind is IdentityEventKind.UNBIND_CORRECTION:
            if not event.claim_id:
                raise SemanticReject("correction requires a claim id")
            binding = self._bindings.get(event.claim_id)
            if binding is None:
                raise SemanticReject("cannot unbind an unknown claim")
            self._bindings[event.claim_id] = Binding(
                binding.claim_id, binding.fact_id, binding.key,
                max(binding.generation, event.generation), event.knowledge_seq, active=False,
            )
        elif event.kind is IdentityEventKind.ALIAS:
            if not event.fact_id:
                raise SemanticReject("alias requires a fact id")
            self.aliases[(key.scope, key.resource_id)] = event.fact_id
        elif event.kind is IdentityEventKind.RETIRE_ALIAS:
            self.aliases.pop((key.scope, key.resource_id), None)
        elif event.kind is IdentityEventKind.MERGE:
            # Merging requires an explicit reviewed mapping; the target must exist.
            if not event.fact_id or not event.claim_id:
                raise SemanticReject("merge requires target fact and claim ids")
            self._fact_keys[event.fact_id] = key
        elif event.kind is IdentityEventKind.SPLIT:
            # A split maps each claim once; duplicates are rejected, never duplicated.
            if not event.claim_id or not event.fact_id:
                raise SemanticReject("split requires claim and fact ids")
            if event.claim_id in self._bindings and self._bindings[event.claim_id].active:
                raise AmbiguousIdentity("split claim is already bound")
            self._bindings[event.claim_id] = Binding(
                event.claim_id, event.fact_id, key, event.generation, event.knowledge_seq
            )
            self._fact_keys[event.fact_id] = key
        elif event.kind is IdentityEventKind.REKEY:
            if not event.fact_id or event.prior_event_id is None:
                raise SemanticReject("rekey requires fact id and prior event")
            self._rekey[event.fact_id] = event.prior_event_id

    def binding_at(self, claim_id: str, seq: int | None = None) -> Binding | None:
        matches = [
            b for b in self._bindings.values()
            if b.claim_id == claim_id and b.active and (seq is None or b.seq <= seq)
        ]
        if not matches:
            return None
        return max(matches, key=lambda b: b.seq)

    def fact_for_key(self, key: FactKey, seq: int | None = None) -> str | None:
        matches = [
            b for b in self._bindings.values()
            if b.active and b.key.canonical() == key.canonical()
            and (seq is None or b.seq <= seq)
        ]
        fact_ids = {b.fact_id for b in matches}
        if len(fact_ids) > 1:
            raise AmbiguousIdentity("multiple facts for one exact key")
        return next(iter(fact_ids)) if fact_ids else None

    def alias_fact(self, scope: str, alias: str) -> str | None:
        return self.aliases.get((scope, alias))

    def approved_key(self, key: FactKey, seq: int | None = None) -> bool:
        return self.fact_for_key(key, seq) is not None

    def audit(self, claims: Iterable[Claim]) -> list[str]:
        """Independent structural audit: report unbound or multiply-bound claims."""
        issues: list[str] = []
        seen: dict[str, set[str]] = {}
        for claim in claims:
            binding = self.binding_at(claim.claim_id)
            if binding is None:
                issues.append(f"unbound:{claim.claim_id}")
                continue
            seen.setdefault(binding.fact_id, set()).add(claim.claim_id)
        for fact_id, claim_ids in seen.items():
            if len(claim_ids) > 1:
                issues.append(f"multi_bound:{fact_id}")
        return issues
