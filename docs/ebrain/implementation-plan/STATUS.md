# Milestone and checkpoint status

Status as of 2026-11-25 (latest real-Postgres run `20261125T055229Z-pg-integration`, [manifest](evidence/20261125T055229Z-pg-integration/manifest.json)):
**V3 implementation is written and synthetically tested; it is NOT released, NOT deployed and NOT production-certified.**
Legacy M0-M6 service remains intact and its compatibility suite still passes.
All V3 HTTP/model/vector/company-routing flags remain disabled by default.

| Milestone | Checkpoint IDs | Status | Evidence / resume point |
| --- | --- | --- | --- |
| Planning/cleanup | Inventory, archive, relocation, document integrity and post-cleanup checks | PASS | [Frozen evidence](evidence/README.md); unchanged |
| M7 | CP7.1-CP7.6 | 5 PASS, 1 BLOCKED_DECISION | [M7 harness evidence](evidence/M7/20261125T024041.368866Z-eea3b228/manifest.json). D01/D03 approved in owner handover; D09 sealed evaluator isolation still NOT_CONFIGURED. |
| M8 | CP8.1-CP8.7 | 7 PASS | [Real Postgres evidence](evidence/20261125T055229Z-pg-integration/manifest.json): 22 integration tests passed with restricted roles, 15 tables and 15 FORCE RLS policies. |
| M9 | CP9.1-CP9.6 | 4 PASS, 2 BLOCKED_DECISION | [Identity/filing code](../../../ebrain/v3/identity/), tests in [v3 suite](evidence/20261125T024900Z-v3integrated/v3-suite.txt). Resume: D02/D07/D08; labelled calibration corpus. |
| M10 | CP10.1-CP10.6 | 3 PASS, 2 IN_PROGRESS, 1 BLOCKED_DECISION | [Retrieval code](../../../ebrain/v3/retrieval/). Resume: scoped FTS + delta overlay, adaptive widening thresholds, D02/D07 index manifest. |
| M11 | CP11.1-CP11.7 | 6 PASS, 1 BLOCKED_DECISION | [Pure reducer](../../../ebrain/v3/resolver/), [review workflow](../../../ebrain/v3/review/workflow.py). Resume: D08 routing/staffing; differential random histories. |
| M12 | CP12.1-CP12.6 | 5 PASS, 1 NOT_RUN | [Projections](../../../ebrain/v3/projections/), [consolidate](../../../ebrain/v3/workers/consolidate.py). Resume: measured ablations/human-minutes per 1k facts. |
| M13 | CP13.1-CP13.7 | 1 PASS, 2 BLOCKED_DECISION, 2 BLOCKED_ENVIRONMENT, 1 IN_PROGRESS, 1 NOT_RUN | [Client adapters](../../../ebrain/v3/clients/), [security tests](../../../tests/v3/security/), [restore tool](../../../tools/ebrain/operations/restore.py). Resume: D10 identity provider; RLS/security/load/restore drills. |
| M14 | CP14.1-CP14.7 | 3 PASS, 1 BLOCKED_DECISION, 3 NOT_RUN | [Web evidence](evidence/M14-web-v3/20261125T075902/summary.md), [quota/tier code](../../../ebrain/v3/quotas/plans.py), [migration tool](../../../tools/ebrain/operations/migrate.py). Resume: authenticated server boundary; sealed acceptance; authorized pilot/cutover. |

## Executed results (exact)

| Check | Command / cwd | Result |
| --- | --- | --- |
| Full API + V3 (CSV sources configured) | `python -m pytest tests -q` from `one-for-all-api`, `EBRAIN_FACTS_SOURCES` set to the three retained CSVs | **157 passed, 17 skipped, 1 warning**, exit 0 |
| V3 suite only | `python -m pytest tests/v3 -q` | **85 passed, 17 skipped, 1 warning**, exit 0 (skips are Postgres-gated and are NOT_RUN) |
| Mandatory-ID discovery | `python tools/ebrain/scripts/validate_v3_gate.py --discover-only` | 29 named pytest IDs discovered, missing=[], exit 0; M07 Playwright alias passed separately |
| Full release gate, no env DSNs | `python tools/ebrain/scripts/validate_v3_gate.py` | exit 2 (blocked): 29/29 discovered, 17 Postgres cases NOT_RUN. [Report](evidence/20261125T031000Z-v3final/gate-report.json) |
| Real Postgres integration suite | `python -m pytest tests/v3/integration -q` via `tools/ebrain/operations/run_pg_integration.py` | **22 passed, exit 0**; restricted roles, 15 tables, 15 FORCE RLS policies. [Manifest](evidence/20261125T055229Z-pg-integration/manifest.json) |
| Full mandatory gate with injected test DSNs (same process) | `python tools/ebrain/scripts/validate_v3_gate.py` | **exit 0, `execution=PASS`, `skipped_present=false`, 29/29 discovered**. [Output](evidence/20261125T055229Z-pg-integration/gate-output.txt) |
| Frozen harness self-tests | `python -m pytest tools/ebrain/legacy/benchmark/tests -q` | 12 passed, exit 0 |
| Frozen 1k baseline, seed 101, reference + product | `Invoke-LegacyBenchmark.ps1` | both exit 0; separate subprocesses, distinct digests |
| Frozen 10k baseline, seeds 101/102/103, reference + product | `Invoke-LegacyBenchmark.ps1` | all six exit 0; one earlier combined command timed out before completion and was rerun separately for product/10k/103 |
| M7 harness/contract tests | `python -m pytest tests/v3/test_eval_protocol.py tests/v3/test_contracts_v3.py -q` | 24 passed (subagent run), exit 0; two traceability alias tests added and re-verified in full suite |
| Web build/typecheck/arch/lint | `npm run typecheck`, `check:arch`, `lint`, `build` from `one-for-all-web` | all exit 0; 2 pre-existing unrelated warnings |
| Web V3 Playwright | `npx playwright test tests/e-brain-v3.spec.ts` | 12 passed after the M07 traceability alias was added (11 from subagent + alias) |

## Not run / blocked (never reported as PASS)

- **Real isolated PostgreSQL is now VERIFIED**: 22 integration cases pass against the disposable `ebrain-v3-test-pg` container with synthetic restricted roles. The owner's session DSN variables were absent from the implementation shell, so synthetic test roles were created in the disposable DB (owner roles untouched; passwords held in-process and never printed or written). RLS, row-lock races and outbox replay are demonstrated. Power-loss durability and real backup/restore remain NOT_RUN.
- **Live models / external provider**: no paid or external model invoked; vector, rerank and semantic filing remain disabled. Model suggestion code is a strict boundary with a disabled default.
- **Sealed evaluation**: commitment/retirement mechanics tested; no independent evaluator, sealed seed or hardware manifest configured.
- **Load, 200 sessions, latency SLOs**: only a declared manifest exists; no measured p50/p95/p99 or resource numbers.
- **Real users, personal data, production migration/deployment/payment**: not authorized, not performed.
- **Full `/e-brain` route**: web slice is additive and props-only; the existing owner route and uncommitted work were not modified.

## Per-checkpoint record

See [CHECKPOINTS.csv](CHECKPOINTS.csv) for all 52 checkpoints with status, evidence, blocker and exact resume task.
See [TRACEABILITY.csv](TRACEABILITY.csv) for the 30 named findings and their executed/gated status.

## Resume point for the next session

1. Postgres integration is green; next close D09 sealed-evaluator isolation, then D02/D07 model manifests and calibration. Re-run `tools/ebrain/operations/run_pg_integration.py` whenever schema/ledger code changes.
2. Resolve D09 (independent sealed evaluator), D02/D07 (local model manifest), D08 (review ownership), D10 (OIDC/SCIM) with concrete owner decisions. Code behind flags is ready; activation awaits approval.
3. Implement remaining independent slices: scoped FTS + committed-delta overlay (CP10.2), adaptive widening (CP10.4), promotion workflow (CP13.2), runbooks (CP13.7), facts generator/pilot (CP14.6), authenticated web server boundary (CP14.2).
4. Re-run the mandatory gate without skips before any release claim: `python tools/ebrain/scripts/validate_v3_gate.py`.

## Individual Developer Edition (owner scope change, 2026-11-25)

See [scope addendum](../INDIVIDUAL_EDITION_SCOPE.md). Enterprise items are
`OUT_OF_SCOPE_CURRENT_RELEASE`, never marked PASS. No production activation.

| Deliverable | Actual result | Evidence |
| --- | --- | --- |
| Real PostgreSQL + restricted roles | 22/22 integration tests passed; 15 tables, 15 FORCE RLS policies; PostgreSQL 16.16, pgvector 0.8.7 | [PG run](evidence/20261125T060107Z-pg-integration/manifest.json) |
| Mandatory gate | 29/29 discovered, `execution=PASS`, zero skips, exit 0 | [gate output](evidence/20261125T060107Z-pg-integration/gate-output.txt) |
| Full regression suite | 162 passed, 17 skipped (no DSNs in that shell), 1 warning | latest `pytest tests -q` with CSV sources |
| Individual benchmark (synthetic, in-process service) | 1k: joint exact 1.00, p95 4-35 ms; 10k: joint exact 1.00, p95 70 ms at 1 session, 306 ms at 3, 537 ms at 5. Context tokens median 3. **The provisional <200 ms p95 target is met at 1k and at 10k/1-session, and FAILS at 10k/3-5 agent sessions.** | [benchmark.json](evidence/individual-benchmark/benchmark.json) |
| Approved local models | E5-small, BGE-small-en, MiniLM cross-encoder artifacts downloaded and SHA-256 pinned; **not calibrated, not activated** | [model-manifest.json](evidence/models/model-manifest.json) |
| Four-client schema-3 support | CLI (`python -m ebrain.v3.cli --enable-v3-local`), MCP (`ebrain.v3.mcp.McpServer`), voice (`EBrainV3PackClient`), web additive `v3-preview` slice. All share V3Service; legacy schema 1 intact. Live agent/web authenticated sessions NOT_RUN. | tests in [v3 suite](evidence/20261125T060107Z-pg-integration/gate-output.txt) |
| Sanitized local pilot | 5 sanitized OFA engineering facts; cross-session retrieval from two different agent identities = correct; authorized revision applied and history retains prior value; local labels only, **not independent** | [pilot.json](evidence/individual-pilot/pilot.json) |
| Encrypted backup + isolated restore | AES-256-GCM backup, SHA-256 verified, restored into separate disposable DB, counts match, 15 RLS policies restored; synthetic in-process key (owner key custody pending) | [backup manifest](evidence/backup-drill/20261125T055939Z-backup-drill/manifest.json) |
| Sealed independent evaluation | **NOT_RUN**: no genuinely isolated evaluator workspace/ACL could be established in this session | no evidence |

### Exact startup and usage

```powershell
# API workspace; PostgreSQL container already running on 127.0.0.1:55432.
cd one-for-all-api
.\.venv\Scripts\python.exe -m pytest tests/v3 --ignore=tests/v3/integration -q
.\.venv-ebrain-test\Scripts\python.exe tools/ebrain/operations/run_pg_integration.py
.\.venv\Scripts\python.exe -m ebrain.v3.cli --enable-v3-local remember --op-id demo1 --resource-id memory-backend --value postgresql-16
.\.venv\Scripts\python.exe -m ebrain.v3.cli --enable-v3-local pack --text "memory backend"
.\.venv\Scripts\python.exe tools/ebrain/operations/pilot_demo.py
.\.venv-ebrain-test\Scripts\python.exe tools/ebrain/operations/backup_drill.py
```

Web preview: `cd one-for-all-web; npm run dev`, open `/v3-preview` (labelled PREVIEW;
not authenticated). `get by` the four-client matrix in the gates above.

### Remaining blockers (individual edition)

- **Sealed evaluation NOT_RUN**: needs a genuinely isolated OpenCode evaluator workspace with hidden labels and pre-run commitment.
- **Model activation gated**: hashes pinned but calibration, offline latency parity and per-arm recall not measured; vector/rerank disabled.
- **Latency target missed at 10k with 3-5 concurrent agent sessions**; requires retrieval indexing optimization, not a target change.
- **Live agent sessions NOT_RUN**: no real OpenCode/Claude/Codex/voice transcript with owner participation.
- **Owner key custody**: backup key is synthetic and in-process; no persistent encrypted backup under owner-controlled key.
- **Web `/e-brain` route**: schema-3 UI exists as additive preview; full route integration needs owner-uncommitted component reconciliation.

## Blocker closure (same timebox, verified)

The six blockers above were worked to completion:

1. **Sealed evaluation**: executed with a pre-run SHA-256 commitment, hidden
   labels in a restricted directory outside the workspace, aggregate-only result
   and zero label disclosure. [report](evidence/sealed-evaluation/sealed-report.json),
   [commitment](evidence/sealed-evaluation/commitment.json). Isolation is
   **procedural**, not a human-independent audit; that limitation is explicit.
2. **Model calibration**: approved artifacts pinned by SHA-256 and calibrated on
   300 development facts / 120 queries. Semantic recall@5 was **0.1167**, below
   the 0.99 gate, so vector/rerank remain explicitly **NOT ACTIVATED** and
   exact/lexical stays authoritative. [models](evidence/models/model-manifest.json),
   [calibration](evidence/calibration/calibration.json).
3. **Latency FAIL closed**: added a disposable scoped (scope, predicate,
   resource) candidate index; 10k p95 fell from ~537 ms to **1.63 ms** at five
   concurrent same-owner sessions, joint exact still 1.00.
   [benchmark](evidence/individual-benchmark/benchmark.json).
4. **Live sessions**: two independent CLI processes share the authoritative
   PostgreSQL ledger (`--persistent`); write in process A, read in process B
   passes. [transcript](evidence/20261125T063556Z-pg-integration/live-cli-output.txt).
   Real voice/human-browser sessions remain unavailable and are NOT_RUN.
5. **Key custody**: AES-256 key stored in a restricted local file outside the
   synced workspace; encrypt → isolated restore → count/RLS verification passes.
   [backup manifest](evidence/backup-drill/20261125T062042Z-backup-drill/manifest.json).
6. **Web `/e-brain`**: additive schema-3 route panel wired into the real
   component behind `NEXT_PUBLIC_EBRAIN_V3=1`, runtime-guarded, no browser token.
   Typecheck/arch/lint/build and 12 Playwright tests pass. Local-only, not an
   authenticated company deployment.

Final gates after these changes: **22/22 PostgreSQL integration, 162 passed full
suite, 12 Playwright, mandatory gate exit 0 with zero skips, plan validator 0
errors**. No production deployment, external inference or data migration.

## Loophole audit and fixes (2026-11-25, continued)

- **Benchmark counted events, not distinct facts**: generator reused resource IDs,
  so "50k memories" was ~15k distinct keys. Fixed to one unique qualified key per
  memory; the manifest now records `distinct_qualified_facts` equal to the size.
- **Loose correctness check**: accuracy previously used a substring test. Now
  joint exact requires exactly one `current` item with the exact expected value
  and `complete` status.
- **O(n²) in-memory write path**: every write rescanned all claims to build the
  candidate index, causing a 10-minute timeout at 50k. Replaced with O(1)
  claim-by-ID lookup.
- **Real Postgres query was loading the whole ledger per query** (p95 960 ms at
  10k). Added a SQL-side exact-key filter and a single-connection query bundle
  (snapshot + claims + control counts). Measured p95: 68 ms → 11 ms at smaller
  sizes after further connection-pooling work.
- **Connection churn per write**: PostgresLedger opened a new DB connection for
  every admitted fact. Now one transaction-managed pooled connection per ledger
  instance, with transaction-local RLS context still set on every operation.
- **Erasure gap on Postgres**: `suppress()` was only implemented on the in-memory
  ledger. Added an append-only Postgres suppression tombstone that marks claims
  suppressed, emits an outbox job and advances the commit cut.
- **Suppression query lacked org context**: fixed `suppressed_ids(org_id)` and
  removed its unsafe use from the Postgres query path (claims are filtered by
  `suppressed=false` in SQL).
- **`10K+` badge**: a case-insensitive search of all web/API source found no such
  literal; it is not rendered by E-Brain V3 code.
- **50,000 facts on real PostgreSQL: DONE.** `pg_scale_check.py --facts 50000
  --queries 200` wrote 50,000 distinct qualified facts through the product
  ledger with the restricted runtime role, answered 200/200 exact queries
  (joint exact 1.00), p50 11.96 ms, p95 21.52 ms; writes took 1849.73 s.
  Evidence: [pg-scale-50000.json](evidence/pg-scale/pg-scale-50000.json).
