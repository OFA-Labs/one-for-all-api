# 09 Test plan

**Test files.** All backend tests are the files in `FINAL/reference/impl/tests/`, copied unchanged to `one-for-all-api/tests/`:
- `conftest.py`
- `test_store.py`, `test_final.py`, `test_tenancy.py`, `test_tags.py`, `test_facts.py`, `test_api.py`

M2 adds `test_bridges.py` (M2/M5 rows below). Web tests are in `one-for-all-web/tests/`.

## 1. Requirements → tests → milestone

| Req | Statement (RFC 2119) | Tests | M |
|---|---|---|---|
| R-001 | The store MUST create exactly the 02 DDL (column order included) | T-001 | M1 |
| R-002 | `write` MUST reject malformed values and an op_id reused with different content, and MUST accept an identical resend | T-002 | M1 |
| R-003 | Ingest MUST redact secrets and set `untrusted`/`injection`/`spoof` before storage | T-003 | M1 |
| R-004 | Chain assignment MUST follow 04 §2 | T-004 | M1 |
| R-005 | Replay MUST implement T1–T7 (04 §3), including human re-assertion | T-005 | M1 |
| R-006 | T8 MUST be applied in SQL before ranking | T-006 | M1 |
| R-007 | `as_of` MUST answer as of the horizon | T-007 | M1 |
| R-008 | `rollback(t)` MUST make answers at t equal to before | T-008 | M1 |
| R-009 | A bundle MUST fit `token_budget` | T-009 | M1 |
| R-010 | Replay MUST use only viewer-visible ops (ADR-6) | T-010 | M1 |
| R-011 | Acks MUST follow COMMIT; two processes MUST lose no acked write | T-011 | M1 |
| R-012 | A restatement MUST never be more current than its origin | T-012 | M1 |
| R-013 | `store.py`, `models.py` and `facts.py` MUST import only the stdlib (no network modules) | T-013 | M1 |
| R-014 | Every row MUST carry `user_id`; `op_id` MUST be unique per user | T-001, T-015 | M1 |
| R-015 | `rollback`, `maintain` and traces MUST be scoped to the Store's user (and project when given) | T-016, T-017 | M1 |
| R-016 | `Store(path)` MUST treat `path` as a directory holding `ebrain.sqlite` | T-011 | M1 |
| R-020 | `limits` MUST report `near_limit` for soft < n ≤ hard | T-020 | M1 |
| R-021 | `limits` MUST report `beyond_tested_range` for n > hard; `capacity_mode=reject` MUST reject writes at n ≥ hard | T-020, T-021 | M1 |
| R-022 | Above hard, every bundle item MUST carry `beyond_tested_range`, and so MUST the header | T-022 | M1 |
| R-023 | `GET /v1/ebrain/limits` MUST return `{**limits_facts.json, **Store.limits}` | T-023 | M1 |
| R-024 | `limits_facts.json` MUST equal `ebrain.facts.build(...)` over the measured CSVs | T-024 | M1 |
| R-025 | Without a valid `EBRAIN_TOKENS` every request MUST be 401, and `ebrain.api` MUST still import | T-025 | M1 |
| R-026 | Shape errors MUST be 422; semantic rejections MUST be 200 with `accepted:false` | T-026 | M1 |
| R-027 | `/resolve` MUST write a human re-assertion that becomes current | T-027 | M1 |
| R-028 | The API MUST open one Store per request and none elsewhere | T-028 | M1 |
| R-029 | `project`/`project_id` MUST default to `"one-for-all"` | T-023 | M1 |
| R-030 | The default heal_mode MUST be `propose`; proposals MUST NOT change answers | T-030 | M1 |
| R-031 | An approved proposal MUST hide the head from its ts; rollback MUST undo it | T-031 | M1 |
| R-032 | `heal_mode=off` MUST produce no actions | T-032 | M1 |
| R-033 | Human actions on unknown targets MUST raise `UnknownTarget` / HTTP 404 | T-033, T-061 | M1 |
| R-040 | `subject_join` MUST default to `off` and then MUST create no links | T-040 | M1 |
| R-041 | Trigram similarity MUST rank a rewording above an unrelated subject | T-041 | M1 |
| R-042 | Review-band pairs MUST be flagged on both chains, never auto-merged; confirm and split MUST be human actions that rollback undoes | T-043 | M1 |
| R-043 | A near-miss (discriminator clash) MUST NOT auto-join | T-044 | M1 |
| R-044 | `subject_join` MUST stay `off` by default until T-042 passes | T-042 | M6 |
| R-050 | EXPERIMENTAL functions MUST carry `# UNTESTED: … settle:`; capacity keys MUST carry `# LIMIT:` | T-050, T-051, T-052 | M1 |
| R-060 | Identity MUST come from the bearer token (an `agent_id` in the body is ignored); unknown tokens MUST get 401; T8 MUST hold across users | T-060 | M1 |
| R-061 | Only human tokens MAY call human routes (403 otherwise); an agent-sent `authority=human` MUST be stored as `agent` | T-061 | M1 |
| R-070 | The capacity meter MUST show the three states with exact copy, plus an error state | T-070 | M1 |
| R-071 | The badge and can/can't panel MUST render from `/limits` with no hard-coded numbers | T-071 | M3 |
| R-072 | Six badges, a legend, and a why-drawer with provenance MUST render | T-072 | M3 |
| R-073 | The known-flaws panel MUST always render | T-073 | M3 |
| R-074 | The pairs UI MUST show the OFF text when `subject_join=off` and call confirm/split when on | T-074 | M4 |
| R-075 | The self-heal state MUST be visible | T-075 | M3 |
| R-076 | Loading, empty and error states MUST render; axe MUST be clean | T-076 | M3 |
| R-077 | The preview without env vars MUST make no network request | T-077 | M1 |
| R-078 | `npm run check:arch` MUST pass at every milestone | T-078 | M1 |
| R-079 | `/e-brain` MUST keep exactly one `main h1`, and the existing quality suite (which already lists `/e-brain` at L11 and L71) MUST pass | T-079 | M1 |
| R-080 | The Claude Code hooks MUST pack at session start, and capture then maintain at stop | T-080 | M2 |
| R-081 | The Codex AGENTS.md block MUST name the pack and remember commands | T-081 | M2 |
| R-082 | The voice pack MUST be off the turn's critical path and empty when the service is unreachable | T-082 | M5 |
| R-083 | Bootstrap MUST import AGENTS.md and MEMORY.md without manual edits | T-083 | M2 |
| R-090 | SPEC B4.3 (L283) MUST be amended before the page ships | T-090 | M1 |
| R-091 | Delete-my-data MUST remove every row of the user and only that user | T-091 | M1 |
| R-092 | No response may contain an unredacted secret | T-092 | M1 |

## 2. Tests

| Test | Kind | What it checks | Where |
|---|---|---|---|
| T-001 | unit | `PRAGMA table_info` column order per table; `UNIQUE(user_id, op_id)` | `test_tenancy.py::test_T001_schema_matches_02_data_model` |
| T-002 | unit | idempotency and malformed writes | `test_store.py::test_idempotency_and_malformed` |
| T-003 | unit | external `untrusted`, injection, secret redaction | `test_store.py::test_t3_external_never_over_first_party_and_untrusted`, `::test_secret_redacted_at_ingest` |
| T-004 | unit | chain order incl. hijack, stale-base, cross-subject cases | `test_store.py::test_t1_*`, `::test_v2_*` (3 tests) |
| T-005 | unit | T1–T7 and human re-assertion | `test_store.py::test_t1_*` … `::test_t7_*`, `::test_t4_human_resolution_reasserts_existing_value` |
| T-006 | unit | T8 | `test_store.py::test_t8_isolation` |
| T-007 | unit | as_of | `test_store.py::test_path_chain_and_t6_tombstone` |
| T-008 | unit + harness | rollback exactness | `test_store.py::test_heal_and_rollback_exact`; harness `rollback_exact` = 1 |
| T-009 | unit + harness | budget | `test_store.py::test_budget_respected`; harness `budget_violations` = 0 |
| T-010 | unit | private supersession invisible to another agent | `test_final.py::test_T010_*` |
| T-011 | unit | two OS processes, 120/120 acked; `ebrain.sqlite` inside the directory | `test_store.py::test_two_processes_lose_nothing` |
| T-012 | unit | summary restating an old code is not current | `test_store.py::test_t7_*` |
| T-013 | lint | stdlib-only imports | `test_tags.py::test_T013_store_and_models_import_only_stdlib` |
| T-014 | unit | `chains` and `chain_versions` for the UI | `test_final.py::test_T014_chains_and_versions_for_ui` |
| T-015 | unit | the same op_id for two users | `test_tenancy.py::test_T015_*` |
| T-016 | unit | rollback scoped by user and project | `test_tenancy.py::test_T016_*` |
| T-017 | unit | maintain and traces scoped by user | `test_tenancy.py::test_T017_*` |
| T-020 | unit | capacity states and the exact `limits()` dict | `test_final.py::test_T020_*` |
| T-021 | unit | `capacity_mode=reject` | `test_final.py::test_T021_*` |
| T-022 | unit | beyond range is flagged | `test_final.py::test_T022_*` |
| T-023 | API | limits merges facts; default project | `test_api.py::test_T023_*` |
| T-024 | unit | facts JSON shape; equals `build()` when the CSVs are present (skips in one-for-all-api) | `test_facts.py::test_T024_*` (2 tests) |
| T-025 | API | fail closed without tokens; module imports | `test_api.py::test_T025_*` |
| T-026 | API | 422 vs 200 + accepted:false | `test_api.py::test_T026_*` |
| T-027 | API | resolve a T4 conflict | `test_api.py::test_T027_*` |
| T-028 | lint | the only `Store(...)` call in api.py is inside `open_store` | `test_tags.py::test_T028_*` |
| T-030 | unit | default proposal-only | `test_final.py::test_T030_*` |
| T-031 | unit | approve and rollback | `test_final.py::test_T031_*` |
| T-032 | unit | heal off | `test_final.py::test_T032_*` |
| T-033 | unit | UnknownTarget | `test_final.py::test_T033_*` |
| T-040 | unit | join off creates no links | `test_final.py::test_T040_*` |
| T-041 | unit | trigram ordering | `test_final.py::test_T041_*` |
| T-042 | harness ablation | `subject_join` on vs off; pass = zombie_rate lower by ≥ 0.02 and correct_version_acc not lower by > 0.02 on every public seed 101–103 at 1k and on seed 101 at 10k. **Current: FAIL (Δ zombie = 0.000).** | from `benchmark\`: `.\.venv\Scripts\python.exe -m harness.runner --contender ..\FINAL\reference\variants\join_on_heal_auto --size 1000 --seed 101 --out ..\FINAL\reference\results\t042.csv`, repeated for seeds 102 and 103 and for `--size 10000 --seed 101`; compare with `variants\heal_auto` |
| T-043 | unit | review band, confirm, split, rollback | `test_final.py::test_T043_*` |
| T-044 | unit | near miss never merges | `test_final.py::test_T044_*` |
| T-050 | lint | EXPERIMENTAL implies `# UNTESTED:` + `settle:` | `test_tags.py::test_T050_*` |
| T-051 | lint | capacity keys carry `# LIMIT:` | `test_tags.py::test_T051_*` |
| T-052 | lint | the tags are present (≥ 3 UNTESTED, ≥ 6 LIMIT) | `test_tags.py::test_T052_*` |
| T-060 | API | 401 cases; agent from token; other user sees nothing | `test_api.py::test_T060_*` (2 tests) |
| T-061 | API | 403 on human routes; authority downgrade; 404 on approving a missing proposal | `test_api.py::test_T061_*` |
| T-070 | Playwright | meter ok/near/beyond, banner, error | `tests/e-brain.spec.ts` M1 block (07 §7) |
| T-071 | Playwright | badge and can/can't panel | `tests/e-brain.spec.ts` "experimental badge…" |
| T-072 | Playwright | badges, legend, drawer | `tests/e-brain.spec.ts` "badges legend and why drawer" |
| T-073 | Playwright | known flaws | `tests/e-brain.spec.ts` "known flaws panel present" |
| T-074 | Playwright | pairs OFF text | `tests/e-brain.spec.ts` "pairs review off text" |
| T-075 | Playwright | heal pill | `tests/e-brain.spec.ts` "self-heal state visible" |
| T-076 | Playwright | empty state and axe | `tests/e-brain.spec.ts` "empty state and axe" |
| T-077 | Playwright | the existing no-network journey | `npx playwright test tests/journeys.spec.ts` |
| T-078 | arch | dependency-cruiser | `npm run check:arch` |
| T-079 | Playwright | the existing quality suite | `npx playwright test tests/quality.spec.ts` |
| T-080 | integration | with a temp `EBRAIN_DATA_DIR` and the API on a free port, the `SessionStart` command prints a bundle starting `[e-brain memory` and `Stop` stores ≥ 1 op | `tests/test_bridges.py::test_claude_hooks` (M2) |
| T-081 | doc check | `one-for-all-web/AGENTS.md` contains `python -m ebrain pack` and `python -m ebrain remember` | `tests/test_bridges.py::test_codex_block` (M2) |
| T-082 | unit | with the service down, `EBrainPackClient.pack == ""` and `refresh` makes no HTTP call on the calling thread | `one-for-all-api/tests/test_voice_client.py` (M5) |
| T-083 | integration | importing a 3-bullet markdown file gives 3 ops with `path` set | `tests/test_bridges.py::test_bootstrap` (M2) |
| T-090 | doc check | `one-for-all-web/docs/SPEC_ITERATION_1.md` no longer contains "intentionally blank placeholder" | `tests/test_bridges.py::test_spec_amended` (M1 adds this one test file with only this test; M2 adds the rest) |
| T-091 | unit + API | delete-my-data scoped by user | `test_tenancy.py::test_T091_*`, `test_api.py::test_T091_*` |
| T-092 | API | a planted `sk-…` never appears in query or chain responses | `test_api.py::test_T092_*` |

## 3. Commands and current results

| Scope | Command | Result on 2026-11-23 |
|---|---|---|
| Reference, Python 3.12.10 + pins | `<venv312>\Scripts\python.exe -m pytest FINAL\reference\impl\tests -q -p no:cacheprovider` | 52 passed |
| Reference, Python 3.11.15 (benchmark venv) | `benchmark\.venv\Scripts\python.exe -m pytest FINAL\reference\impl\tests -q -p no:cacheprovider` | 43 passed, 1 skipped |
| one-for-all-api layout at M0 (stub store), Python 3.12.10 | `python -m pytest tests -q` | 6 passed, 1 skipped, 22 failed, 23 errors (simulated in a scratch copy of the layout) |
| one-for-all-api layout at M1 (real store), Python 3.12.10 | `python -m pytest tests -q` | 51 passed, 1 skipped (simulated; the skip is T-024 CSV match) |
| Web | `cd one-for-all-web; npm run build; npx playwright test tests/e-brain.spec.ts tests/quality.spec.ts tests/journeys.spec.ts; npm run check:arch` | not run (the web code is not built yet) |
