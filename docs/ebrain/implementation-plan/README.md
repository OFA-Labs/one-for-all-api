# E-Brain V3 implementation plan

This is the implementation entry point for the next coding agent. It plans the move from the **existing M0–M6 experimental SQLite service** to the proposed V3 engineering-memory service. It does not claim V3 is implemented. Prepared 2026-11-24; the owner explicitly selected V3 as the main plan and requested removal of the retired tournament and local voice prototype.

**Start by reading [AGENT_START.md](AGENT_START.md), then [CURRENT_STATE.md](CURRENT_STATE.md).** Continue with [SPEC_RECONCILIATION.md](SPEC_RECONCILIATION.md), [ARCHITECTURE.md](ARCHITECTURE.md), [CONTRACTS.md](CONTRACTS.md), [DECISIONS_REQUIRED.md](DECISIONS_REQUIRED.md) and the milestone README. Do not implement all milestones in one unreviewable change.

## Execution order

| Milestone | Deliverable | Dependency | Current state |
| --- | --- | --- | --- |
| [M7 — evaluation and contracts](milestones/M7-harness-contracts/README.md) | Independent oracle, scalable generator, negative controls, versioned API/schema and ADR proposals | Verified current baseline | NOT STARTED |
| [M8 — ledger and security](milestones/M8-ledger-security/README.md) | Postgres, tenant constraints/RLS, safe ingestion, committed receipts, outbox, pending fences | M7 contract freeze; approved foundation decisions | NOT STARTED |
| [M9 — fact identity and filing](milestones/M9-fact-registry/README.md) | Typed registry, identity ledger, source lifecycle, exact binding and review-only semantic suggestions | M8 storage/security; M7 fixtures | NOT STARTED |
| [M10 — retrieval](milestones/M10-retrieval/README.md) | Protected exact matches, lexical/vector/graph candidates, delta overlay, failure and generation contracts | M9 identity; M8 snapshot interface | NOT STARTED |
| [M11 — resolver and decisions](milestones/M11-resolver-decisions/README.md) | Deterministic authorized current state, temporal reads, conflict and compensating rollback | M8 commit boundary; M9 identity; M7 independent oracle | NOT STARTED |
| [M12 — projections and maintenance](milestones/M12-projections-maintenance/README.md) | Rebuild/reconcile, citations, derived evidence, advisory maintenance | M9 + M11; integrate M10 generations | NOT STARTED |
| [M13 — team security and operations](milestones/M13-team-operations/README.md) | SSO/SCIM, scoped clients/receipts, promotion, security/load/restore drills | M8–M12 integrated | NOT STARTED |
| [M14 — tiers, UI, migration and release](milestones/M14-release/README.md) | Atomic plan budgets, honest UI, complete clients, staged migration and pilot | M13 gates; all earlier checkpoint evidence | NOT STARTED |

M10 may implement candidate discovery before M11, but its authoritative answer integration checkpoint remains pending until M11 passes. M8 must provide minimal pure replay and authorization interfaces; a placeholder card must never be treated as current. M9 uses proposal primitives from M8; M11 adds complete reviewed decisions. M13 establishes company readiness; M14 is the production cutover gate.

Every milestone directory contains a README with ordered tasks, concrete existing/proposed paths, checkpoints, tests, rollback and exit criteria, plus a test-case matrix. [STATUS.md](STATUS.md) tracks overall progress; [TRACEABILITY.csv](TRACEABILITY.csv) maps all 30 V3 findings to named planned tests. Future test files and commands are marked as future work.

[CHECKPOINTS.csv](CHECKPOINTS.csv) contains all **52 checkpoints**, each initialized to NOT_STARTED with evidence/blocker/resume columns. Update it together with milestone evidence; no V3 checkpoint is marked working merely because the legacy suite passes.

## Supporting material

- [VALIDATION.md](VALIDATION.md): commands that work now, commands to build later, evidence and pass/fail rules.
- [MIGRATION_AND_RECOVERY.md](MIGRATION_AND_RECOVERY.md): export, mapping, write fencing, cutover, rollback and erasure.
- [CLEANUP.md](CLEANUP.md): what was retained/removed and how to restore the source archive.
- [Evidence directory](evidence/README.md): observed baseline logs, file hashes and relocation verification.
- [V3 specification](../SPEC_DEV_BRAIN_V3.md): owner-selected proposed product requirements; original contents preserved under their correct versioned filename.
- [Research handoff](../HANDOFF_TO_PLANNER.md): historical research, not current commands after relocation.
- [Retained legacy benchmark](../../../tools/ebrain/README.md): frozen reference, harness, raw research and runnable wrappers.

## Global definition of done

All mandatory checkpoints are PASS with linked evidence; all 30 named regressions are discovered and run without mandatory skips; public and independently controlled sealed evaluation meet the approved targets; migration and recovery rehearsals preserve every accepted event or document a reviewed quarantine; no known unauthorized or stale-current deterministic case passes as current. Real-user claims require separate labelled pilot evidence. Owner approval of a proposed plan is never evidence that a test passed.

No invented pricing, real credential setup, production deployment or data migration is part of this planning change. No new model, database or live Langfuse service dependency was installed. Langfuse dataset-design guidance was used for evaluation structure; [its guide](https://langfuse.com/academy/datasets) separates inputs, expected outputs and review metadata. This plan keeps evaluation artifacts local and requires no Langfuse integration.

## Implementation update (2026-11-25)

This planning document still describes the original proposal. Actual implementation
results, statuses, evidence links and the exact resume point are in
[STATUS.md](STATUS.md) and [CHECKPOINTS.csv](CHECKPOINTS.csv). V3 code is present
behind disabled flags and is synthetically tested; it is **not** a released or
production-certified service, and no Postgres/RLS, sealed, load, pilot or cutover
claim has been made.
