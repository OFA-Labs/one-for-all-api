"""Short individual-developer pilot: cross-session persistence and revision.

Uses sanitized engineering facts from the OFA repositories (no personal data,
no credentials, no raw source). Labels are local and NOT independently assessed;
this is not a sealed evaluation or a real-user study.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from ebrain.v3.auth.context import build_context
from ebrain.v3.clocks import FakeClock
from ebrain.v3.config import V3Config
from ebrain.v3.contracts import Action, ClaimKind, Grant, Principal, Selector, WriteRequest
from ebrain.v3.identity.keys import canonical_key
from ebrain.v3.service import V3Service

API = Path(__file__).resolve().parents[3]
OUT = API / "docs/ebrain/implementation-plan/evidence/individual-pilot"
ORG, SCOPE = "org-demo", "one-for-all"


def session(name: str):
    principal = Principal(
        subject=name, org_id=ORG,
        grants=(Grant(scope=SCOPE, predicates=("*",), actions=tuple(Action),
                      authority="human"),), auth_epoch=1,
    )
    return build_context(principal, request_id=f"pilot-{name}", scope=SCOPE)


def main() -> int:
    svc = V3Service.build(cfg=V3Config(), clock=FakeClock())
    first = session("opencode-session-1")
    second = session("claude-session-2")   # different agent identity, same owner scope
    third = session("codex-session-3")
    facts = [
        ("architecture-root", "decision.status", "active", "api"),
        ("memory-backend", "decision.status", "postgresql", "api"),
        ("web-framework", "service.config.value", "next-16", "web"),
        ("legacy-prototype", "decision.status", "retained-read-only", "api"),
        ("voice-bridge", "decision.status", "optional-off", "api"),
    ]
    for resource, predicate, value, repo in facts:
        key = canonical_key(
            org_id=ORG, scope=SCOPE, resource_namespace="repo",
            resource_id=resource, predicate=predicate,
            kind=ClaimKind.ASSERTION,
            qualifiers={"repo": f"one-for-all-{repo}", "environment": "dev"},
        )
        svc.write(first, WriteRequest(
            op_id=f"p-{resource}", key=key, value=value, source_id="sanitized-repo-docs",
            source_revision="1", idempotency_key=f"p-{resource}",
            valid_from="2025-01-01T00:00:00+00:00",
        ))

    def ask(ctx, resource: str, predicate: str, repo: str):
        selector = Selector(
            scope=SCOPE, predicate=predicate, resource_id=resource,
            qualifiers=(("repo", f"one-for-all-{repo}"), ("environment", "dev")),
        )
        return svc.query(ctx, selector)

    checks = []
    for ctx in (second, third):
        answer = ask(ctx, "memory-backend", "decision.status", "api")
        checks.append({
            "session": ctx.principal.subject,
            "answer_status": answer.answer_status.value,
            "current": [i.current_value for i in answer.items
                        if i.state.value == "current"],
            "expected": "postgresql",
        })
    # Authorized revision with expected head from the persisted claim.
    old_claim = svc.ledger.load_slice(first, (), svc.ledger.seq)[1]
    revised_key = canonical_key(
        org_id=ORG, scope=SCOPE, resource_namespace="repo",
        resource_id="memory-backend", predicate="decision.status",
        kind=__import__("ebrain.v3.contracts", fromlist=["ClaimKind"]).ClaimKind.ASSERTION,
        qualifiers={"repo": "one-for-all-api", "environment": "dev"},
    )
    receipt = svc.write(third, WriteRequest(
        op_id="p-revision", key=revised_key, value="postgresql-16",
        source_id="sanitized-repo-docs", source_revision="2",
        idempotency_key="p-revision", expected_head=old_claim.claim_id,
        valid_from="2025-02-01T00:00:00+00:00",
    ))
    after = ask(second, "memory-backend", "decision.status", "api")
    history_cut = after.snapshot.knowledge_seq - 1
    before_answer = svc.ledger.load_slice(second, (revised_key,), history_cut)
    report = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "scope_note": "sanitized engineering facts; local labels; not independently evaluated",
        "facts_written": len(facts),
        "cross_session_checks": checks,
        "revision_receipt": {"status": receipt.status.value, "seq": receipt.knowledge_seq},
        "after_revision_current": [i.current_value for i in after.items
                                   if i.state.value == "current"],
        "historical_value_at_prior_cut": [c.value for c in before_answer],
        "pass": (
            all(c["current"] == ["postgresql"] for c in checks)
            and receipt.status.value == "applied"
            and [i.current_value for i in after.items if i.state.value == "current"]
            == ["postgresql-16"]
            and "postgresql" in [c.value for c in before_answer]
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pilot.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
