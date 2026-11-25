# E-Brain V3 individual edition — loophole audit

Date 2026-11-25. Each item below is a defect I found by re-reading the
implementation and measurement code, with the pain point and the fix actually
applied. Evidence paths are relative to this repository.

| # | Loophole / pain point | Fix applied | Evidence / verification |
| --- | --- | --- | --- |
| 1 | "50k memories" benchmark reused resource IDs, producing only ~15k distinct qualified keys — inflated scale claim. | One unique stable resource per memory; manifest now records `distinct_qualified_facts` and equals the configured size. | `docs/ebrain/implementation-plan/evidence/individual-benchmark/benchmark.json` |
| 2 | Accuracy used a substring check, so a multi-fact answer containing the right value could pass. | Joint exact requires exactly one `current` item, the exact expected value and `complete` status. | same benchmark manifest |
| 3 | In-memory write path rescanned all claims to build the candidate index; 50k timed out after 10 min. | O(1) `claim_by_id` lookup; candidate index updated in constant time. | benchmark rerun 1k/10k/50k completed |
| 4 | Postgres query loaded the whole claim table per query; p95 960 ms at 10k. | SQL-side exact-key filter plus a one-connection query bundle (snapshot + claims + control counts). | `docs/ebrain/implementation-plan/evidence/pg-scale/pg-scale-10000.json` |
| 5 | PostgresLedger opened a new DB connection for every admitted fact (~19 facts/s). | One transaction-managed pooled connection per ledger instance; RLS context still set transaction-locally on each operation. | `pg-scale-1000.json` write time dropped from 51 s to 27.5 s |
| 6 | Erasure existed only on the in-memory ledger; Postgres had no suppression path. | Append-only `suppress()` tombstone marks claims suppressed, emits outbox job and advances the commit cut. | integration test `test_postgres_suppression_removes_current` |
| 7 | `suppressed_ids` read across all orgs without RLS context. | Now takes `org_id` and sets the scoped transaction context; Postgres query path filters `suppressed=false` in SQL instead. | code + integration suite |
| 8 | Reviewed decisions were stored only in the in-process review service; the resolver never saw them. | `V3Service.query` merges review decisions with ledger decisions, filtered to the authorized scope. | code + resolver tests |
| 9 | `apply()` changed the review record but did not persist an authoritative control event. | `V3Service.apply` now calls `ledger.record_decision`, implemented on both ledgers with `ON CONFLICT` idempotency. | code + integration suite |
| 10 | `Vote.voter` was client-supplied; a caller could cast a vote under another principal's name. | Vote voter must equal the authenticated principal; tests updated to use matching contexts. | `tests/v3/test_resolver_v3.py`, `tests/v3/integration/test_review_approval.py` |
| 11 | Review decisions from other scopes could affect a scoped query. | Decision merge filtered by `d.scope == ctx.scope`. | code |
| 12 | Sealed report claimed "hidden labels compared" although generated hidden values were salt-only and unused. | Hidden expected outputs are generated and committed before the candidate runs, then actually compared; report states the limitation (commitment/no-leak regression, not a held-out semantic challenge). | `docs/ebrain/implementation-plan/evidence/sealed-evaluation/sealed-report.json` |
| 13 | Backup AES key had only `chmod(0600)`, which is advisory on Windows, and sat in a synced-user temp path. | Key stored outside OneDrive with `icacls /inheritance:r /grant:r <user>:(F)`; manifest records ACL status, never key bytes. | `docs/ebrain/implementation-plan/evidence/backup-drill/20261125T062042Z-backup-drill/manifest.json` |
| 14 | Request digest omitted `kind`, so idempotency could replay a different claim kind. | `kind` included in the digest on both MemoryLedger and PostgresLedger. | code |
| 15 | Single-user owner exception was defined but never reachable in the review workflow. | Explicit `enable_local_single_user_exception(reason, isolated_local, synthetic)` with audit log; production/pilot use refused. | `test_D08_governance_sla_and_single_user_exception` |
| 16 | `10K+` badge could not be traced to product code. | Case-insensitive search of all web/API source found no such literal; it is not rendered by E-Brain V3. | search result recorded in STATUS.md |

## 50k Postgres result (completed)

`tools/ebrain/operations/pg_scale_check.py --facts 50000 --queries 200`:
**50,000 distinct facts written through the product ledger with the restricted
runtime role**, 200 exact queries, **200/200 correct (joint exact 1.00)**, p50
11.96 ms, **p95 21.52 ms**, write time 1849.73 s. Evidence:
`docs/ebrain/implementation-plan/evidence/pg-scale/pg-scale-50000.json`.

## Remaining honest gaps
- Semantic/vector/retrieval model activation remains gated by the failed recall
  calibration (0.1167 < 0.99).
- Sealed evaluation is procedural isolation, not a human-independent audit.
- No real voice or authenticated human-browser session has been run.
