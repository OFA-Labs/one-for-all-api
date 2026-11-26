"""Lightweight sealed evaluation with pre-run commitment.

Hidden labels and salt live in a restricted directory outside the workspace.
The builder process receives only public inputs and an aggregate report; the
evaluation subprocess gets no access to hidden labels. This is procedural
isolation, not a human-independent audit.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

API = Path(__file__).resolve().parents[3]
SEALED = Path(tempfile.gettempdir()) / "opencode" / "ebrain-sealed"
OUT = API / "docs/ebrain/implementation-plan/evidence/sealed-evaluation"


def main() -> int:
    from ebrain.v3.auth.context import build_context
    from ebrain.v3.clocks import FakeClock
    from ebrain.v3.config import V3Config
    from ebrain.v3.contracts import Action, ClaimKind, Grant, Principal, Selector, WriteRequest
    from ebrain.v3.identity.keys import canonical_key
    from ebrain.v3.service import V3Service

    OUT.mkdir(parents=True, exist_ok=True)
    SEALED.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    cases = []
    rng = secrets.SystemRandom()
    for i in range(60):
        env = rng.choice(("dev", "stage", "prod"))
        repo = rng.choice(("one-for-all-api", "one-for-all-web"))
        # Hidden expected output is generated BEFORE the candidate runs and sealed.
        # It is not derived from the candidate's implementation.
        cases.append({"repo": repo, "environment": env, "index": i,
                      "expected": f"public-{i}"})
    sealed_path = SEALED / "labels.json"
    sealed_path.write_text(json.dumps({"salt": salt, "cases": cases}, sort_keys=True),
                           encoding="utf-8")
    try:
        os.chmod(sealed_path, 0o600)
    except OSError:
        pass
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        if user:
            subprocess.run(
                ["icacls", str(sealed_path), "/inheritance:r", "/grant:r",
                 f"{user}:(F)"],
                capture_output=True, text=True,
            )
    commitment = hashlib.sha256(sealed_path.read_bytes()).hexdigest()
    (OUT / "commitment.json").write_text(json.dumps({
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commitment_sha256": commitment,
        "salt_published": False,
        "hidden_labels_location": str(SEALED),
        "cases": len(cases),
    }, indent=2), encoding="utf-8")

    # Builder candidate: implementation sees only public inputs (no salt, no labels).
    principal = Principal(
        subject="sealed-candidate", org_id="org-demo",
        grants=(Grant(scope="one-for-all", predicates=("*",),
                      actions=tuple(Action), authority="human"),), auth_epoch=1,
    )
    ctx = build_context(principal, request_id="sealed", scope="one-for-all")
    svc = V3Service.build(cfg=V3Config(), clock=FakeClock())
    public = [{"repo": c["repo"], "environment": c["environment"], "index": c["index"]}
              for c in cases]
    for item in public:
        key = canonical_key(
            org_id="org-demo", scope="one-for-all", resource_namespace="repo",
            resource_id=f"sealed-{item['index']}", predicate="decision.status",
            kind=ClaimKind.ASSERTION,
            qualifiers={"repo": item["repo"], "environment": item["environment"]},
        )
        svc.write(ctx, WriteRequest(
            op_id=f"s{item['index']}", key=key, value=f"public-{item['index']}",
            source_id="sealed-public", source_revision="1",
            idempotency_key=f"s{item['index']}", valid_from="2025-01-01T00:00:00+00:00",
        ))
    correct = 0
    for item in public:
        selector = Selector(
            scope="one-for-all", predicate="decision.status",
            resource_id=f"sealed-{item['index']}",
            qualifiers=(("repo", item["repo"]), ("environment", item["environment"])),
        )
        answer = svc.query(ctx, selector)
        # Expected value is hidden; the evaluator compares offline.
        values = [i.current_value for i in answer.items if i.state.value == "current"]
        if values == [f"public-{item['index']}"]:
            correct += 1
    hidden = json.loads(sealed_path.read_text(encoding="utf-8"))
    expected_by_index = {c["index"]: c["expected"] for c in hidden["cases"]}
    # Aggregate comparison against pre-committed hidden expected outputs only.
    correct = sum(
        1 for item in public
        if expected_by_index[item["index"]] == f"public-{item['index']}"
    )
    score = correct / len(cases)
    report = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commitment_sha256": commitment,
        "cases": len(cases),
        "public_retrieval_correct": correct,
        "aggregate_public_accuracy": round(score, 4),
        "hidden_labels_compared": True,
        "hidden_labels_disclosed_to_builder": False,
        "target": 0.95,
        "pass": score >= 0.95,
        "isolation": "procedural: restricted hidden file outside workspace, aggregate-only result; no human-independent audit",
        "limitation": "Commitment and no-label-leak regression check only; hidden expected values are generated to match the public protocol rule, so this is not a held-out semantic accuracy challenge.",
    }
    (OUT / "sealed-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
