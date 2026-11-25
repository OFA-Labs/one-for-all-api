# M7 — Independent evaluation and versioned contracts

**State: IMPLEMENTED — 5 PASS / 1 BLOCKED_DECISION (2026-11-25).** Evidence: [M7 harness run](../../evidence/M7/20261125T024041.368866Z-eea3b228/manifest.json). D01/D03 principles approved in the owner handover; CP7.6 PASS. Remaining: D09 independent sealed-evaluator isolation and commitment. Dependencies: current baseline and cleanup manifest verified. No V3 product capability is delivered by this milestone alone. Main specification: V3 §§3,15,20–23; findings H05, M01, M04. Older handoff M7/M11/M12 research is input, not the acceptance gate.

## Deliverable

A reproducible evaluation protocol that cannot reward correct-plus-stale answers, a generator supporting both event-count and distinct-fact workloads, an independent oracle, versioned schema fixtures and reviewable ADRs. Keep frozen harness 1.0.0 and CSVs unchanged.

## Existing and proposed files

- Read existing `ebrain/{store,api,models,facts}.py`, `tests/`, web `src/lib/ebrain/`, `tools/ebrain/legacy/benchmark/harness/{generate,scenarios,metrics,truth,runner,loader}.py` and retained raw results.
- Create `tools/ebrain/v3-eval/{README.md,protocol.json,generator.py,oracle.py,metrics.py,runner.py,manifest.py}` with test-only fixtures/models isolated from product imports. Use a separately installable module/project or explicit CLI; document actual invocation.
- Create `tests/v3/test_eval_protocol.py`, `test_contracts_v3.py`, versioned schemas/fixtures under `docs/ebrain/contracts/v3/`, and an immutable baseline manifest. Exact packaging and future CLI are part of CP7.2; do not pretend it exists today.
- Create a machine-readable mandatory test-ID manifest and CI gate (proposed `.github/workflows/ebrain-checks.yml`) that runs legacy tests, restricted-Postgres integration and appropriate public evaluation, asserts discovery and fails on missing/skipped required cases. Keep live-model/large-load/sealed jobs separate with explicit prerequisites and artifact manifests; a job omitted for missing secrets is NOT_RUN, never a green release gate.
- Append proposed ADRs to the existing decisions log; record approval status in the plan.

## Ordered implementation

1. **CP7.1 — freeze the actual baseline.** Run legacy/backend/web checks, hash source including dirty files, record Python/harness versions and original CSV digests. Reproduce 1k and 10k public seeds using the frozen reference and a separately hashed current-product adapter. Never let import caching substitute reference Store for product Store; one contender per subprocess. Establish that T-024 exact facts generation passes with retained CSV paths.
2. **CP7.2 — publish protocol and generator.** Separate `event_count`, `distinct_fact_count`, revision distribution and independent control/identity event counts. Build unique qualified keys for 100k facts and sufficiently many subjects for 100k events (~5k canary chains at size/20). Parameterize rather than monkeypatch. Freeze scenario mix, runtime/timeouts, failure policy, repetitions, hardware boundary and manifest schema. Test deterministic hash at 1k/10k/50k/100k; larger fixtures may stream but must retain exact counts/oracle mapping. Never extrapolate a 100k-event run to 100k facts.
3. **CP7.3 — implement an independent oracle.** Construct expected identity, authorized decisions/observations, effective/knowledge time, concurrency, source lifecycle, conflict and current set from test-owned rules. Do not import production identity/resolver/classifier or show oracle fact IDs/labels to the implementation in silent-alias cases. Legitimate structured keys are allowed only in scenarios designed to provide them. Use human-reviewed miniature histories to validate the oracle independently.
4. **CP7.4 — implement metrics and negative controls.** Joint exact means returned current set equals expected authorized set, correct state/provenance and complete requested facets. Score true+zombie, all-empty, always-current, dropped facets, wrong sources, wrong scope and label-leaking contenders as failures. Report legacy presence alongside joint exact, per-seed/per-scenario denominator, family-aware uncertainty, filing precision/recall/pending, retrieval per-arm/final recall, conflict/as-of, ambiguity/abstention, and actual delivery after clipping.
5. **CP7.5 — freeze development and sealed separation.** Public 101/102/103 are development. Old disclosed championship seeds are no longer secret. Independent evaluator owns a new sealed seed/fact-family/template/repo manifest; implementer sees only commitment hash until final evaluation. Tuning on sealed failure retires that suite and requires a new independent suite. Cache model outputs by sanitized inputs+scope+full manifest, never labels; run live models separately from deterministic recorded replay.
6. **CP7.6 — freeze contracts/ADRs.** Turn CONTRACTS.md into executable strict schema-3 fixtures/OpenAPI, including errors, pending receipts, scoped cursors and compatibility matrix. Draft D01/D02/D03/D09 with exact changes, examples and impact. A rejected architecture decision blocks its activation; evaluation/contract work remains usable.

## Checkpoints and evidence

| Checkpoint | Working when | Required evidence |
| --- | --- | --- |
| CP7.1 | Current/reference imports and source hashes are distinct; baseline reruns and generated facts match their declared inputs | commands, hashes, CSVs, T-024 output |
| CP7.2 | Every required size builds deterministically without catalogue exhaustion; facts/events counted separately | generator tests and dataset manifests |
| CP7.3 | Tiny manually reviewed time/auth/conflict cases agree with independent oracle | reviewed expected outputs + oracle tests |
| CP7.4 | Every intentionally broken contender fails the relevant gate; abstention cannot inflate accuracy | negative-control results |
| CP7.5 | Sealed ownership/commitment and no-label-leak checks are enforceable | protocol and independent evaluator record |
| CP7.6 | Schema/API compatibility fixtures pass; required ADR direction reviewed | contract tests, decision records |

Run current commands in VALIDATION.md first. After creating tests: `.venv\Scripts\python.exe -m pytest tests/v3/test_eval_protocol.py tests/v3/test_contracts_v3.py -q` from API, then the full legacy suite. Provide an actual installed evaluation CLI with `--help` examples and fail-on-threshold behavior before calling this milestone done. Dataset construction is not an accuracy result.

## Rollback / exit

Only new tools/docs/tests and disabled contracts are added; rollback removes their activation without touching frozen files or the live database. M7 PASS requires all six checkpoints and mandatory negative controls. Postgres/model/load proof remains NOT_RUN. Handoff to M8 with approved schema/authority boundary, fixture package, exact invocations, protocol hash and outstanding decisions.
