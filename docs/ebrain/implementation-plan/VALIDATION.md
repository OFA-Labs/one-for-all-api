# Verification commands and evidence rules

Use PowerShell. Paths below start at `one-for-all-api`, unless stated otherwise. Never read `.env` files or print connection/token values. Existing tests use temporary synthetic data; V3 integration tests must use a separate restricted Postgres test database and cannot run against the owner’s real store.

## Commands available now

```powershell
# Full current backend; unskip exact measured-facts verification using retained CSVs.
powershell -NoProfile -File tools/ebrain/scripts/Test-CurrentBackend.ps1

# Frozen harness self-tests, separate from product tests.
& ./.venv/Scripts/python.exe -m pytest tools/ebrain/legacy/benchmark/tests -q

# Separate subprocess per contender; output and source manifest go to evidence.
powershell -NoProfile -File tools/ebrain/scripts/Invoke-LegacyBenchmark.ps1 -Contender reference -Size 1000 -Seed 101
powershell -NoProfile -File tools/ebrain/scripts/Invoke-LegacyBenchmark.ps1 -Contender product -Size 1000 -Seed 101

# Audit plan local links, all 30 finding IDs and frozen relocation hashes.
& ./.venv/Scripts/python.exe tools/ebrain/scripts/validate_plan.py
```

The benchmark wrapper uses API Python 3.12 by default and labels it in its manifest. For original-runtime replication create a **new** isolated Python 3.11 venv from documented pins and pass its absolute interpreter with `-Python`; do not move/copy a venv and assume it remains valid. The original research used 3.11.15/SQLite 3.50.4; exact historical timings cannot be inferred from another runtime/hardware. `reference` means frozen Store; `product` means current API Store with combined source hashes. No shadow import in a shared interpreter.

Run 1k/10k matrices in M7, each seed separately:

```powershell
foreach ($evalSize in @(1000,10000)) {
  foreach ($evalSeed in @(101,102,103)) {
    powershell -NoProfile -File tools/ebrain/scripts/Invoke-LegacyBenchmark.ps1 -Contender reference -Size $evalSize -Seed $evalSeed
    if ($LASTEXITCODE -ne 0) { throw 'Reference benchmark failed' }
    powershell -NoProfile -File tools/ebrain/scripts/Invoke-LegacyBenchmark.ps1 -Contender product -Size $evalSize -Seed $evalSeed
    if ($LASTEXITCODE -ne 0) { throw 'Product benchmark failed' }
  }
}
```

The frozen generator still exhausts at 50k. Retained `legacy/results/run_extended.py` is historical experiment code with a labelled extended catalogue; old `.ps1` drivers contain obsolete absolute paths/venv assumptions and are archived, not active entry points. Their commands require the new prefix and explicit interpreter. The planning task does not rerun the hour-long 50k experiments. M7 builds a separate versioned scalable harness, with its own manifest and no direct numeric comparison across changed scoring definitions.

Web, from `one-for-all-web`:

```powershell
npm run typecheck
npm run check:arch
npm run lint
npm run build
npx playwright test tests/e-brain.spec.ts tests/e-brain-client.spec.ts tests/journeys.spec.ts tests/quality.spec.ts
```

Check each command’s exit code; do not continue and report overall pass if an earlier command failed. Playwright starts a production preview on 127.0.0.1:3100; a conflicting running server is an environment failure. Tests are synthetic preview/client checks. Real browser-to-authenticated-API and actual agent sessions require the dedicated live suite and [existing live checklist](../LIVE_VALIDATION.md). Do not mark those live checks PASS from these mocks. Restore only newly generated tracked screenshots/next-env files known clean in your captured baseline.

## Fresh-pull setup (individual developer edition)

A developer cloning this branch needs no manual SQL migration. The integration
runner creates synthetic restricted roles in the disposable database, applies
`migrations/ebrain_v3/0001_init.sql`, verifies 15 tables/15 FORCE RLS policies and
runs the suite. Credentials are injected into child processes only; they are
never printed or written to a file.

```powershell
cd one-for-all-api
uv venv .venv
uv pip install --python .venv/Scripts/python.exe -r requirements.txt
uv venv .venv-ebrain-test
uv pip install --python .venv-ebrain-test/Scripts/python.exe "psycopg[binary]==3.3.9" cryptography sentence-transformers onnxruntime
# PostgreSQL container ebrain-v3-test-pg on 127.0.0.1:55432 (pgvector/pgvector:pg16) must be running.
.\.venv-ebrain-test\Scripts\python.exe tools/ebrain/operations/run_pg_integration.py
```

For a manual `python -m ebrain.v3.cli --persistent`, set `EBRAIN_V3_TEST_PG_DSN`
in your own shell (the runner's synthetic DSNs are ephemeral by design).
Web: `npm ci` in `one-for-all-web`, then the web commands below.

## What is active for retrieval right now

Semantic/vector/rerank are **disabled** (calibration recall@5 0.1167 < 0.99).
Active path: exact qualified key (protected), scoped lexical token-overlap
candidates, and a pure deterministic resolver over admitted claims, source
status, grants, identity bindings, valid/knowledge cuts and reviewed decisions.
Graph, vector and cross-encoder arms are off; no model runs on the resolver path.

## Commands implemented by the V3 work (2026-11-25)

All paths start at `one-for-all-api` unless stated. V3 routes, models and vector
arms remain disabled; these commands test isolated code and synthetic data only.

```powershell
# Full legacy + V3 suite with T-024 exact facts enabled.
powershell -NoProfile -File tools/ebrain/scripts/Test-CurrentBackend.ps1
# V3 suite only (17 Postgres cases are BLOCKED_ENVIRONMENT/NOT_RUN without a DSN).
& ./.venv/Scripts/python.exe -m pytest tests/v3 -q
# Mandatory 29-finding discovery gate (M07 is a Playwright alias verified separately).
& ./.venv/Scripts/python.exe tools/ebrain/scripts/validate_v3_gate.py --discover-only
# Full release gate: exits 2 while any mandatory case is skipped or missing.
& ./.venv/Scripts/python.exe tools/ebrain/scripts/validate_v3_gate.py
# Versioned evaluation CLI (test-only, no product imports).
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli --help
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli protocol
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli generate --mode distinct_fact_count --size 1000 --seed 101 --stream
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli negative-controls
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli evaluate --adapter tools/ebrain/v3-eval/fixtures/reference_contender.py --size 1000 --seed 101
# Migration and restore rehearsals (synthetic files only).
& ./.venv/Scripts/python.exe -m tools.ebrain.operations.migrate --help
& ./.venv/Scripts/python.exe -m tools.ebrain.operations.restore --help
```

Real Postgres/RLS/concurrency integration (currently **NOT RUN**):

```powershell
# Requires a disposable database, psycopg 3 in an isolated test venv and the DSN
# supplied via the environment variable NAME only (value is never printed).
# $env:EBRAIN_V3_TEST_PG_DSN = '<supplied by operator>'
& ./.venv/Scripts/python.exe -m pytest tests/v3/integration -q
```

Observed results for the implemented commands and their exact evidence links are
in [STATUS.md](STATUS.md) and the
[integrated run manifest](evidence/20261125T024900Z-v3integrated/manifest.json).
Web commands are unchanged and recorded under `evidence/M14-web-v3/`.

## Commands still to implement in future milestones

The remaining scoped FTS + committed-delta overlay (CP10.2), adaptive widening
(CP10.4), promotion workflow (CP13.2), measured ablations (CP12.6), sealed
evaluation (CP14.5), facts generator/pilot (CP14.6) and authenticated web server
boundary (CP14.2) are not claimed as executed. Tests must assert mandatory
discovery/count and fail on a mandatory skip/missing environment; pytest exit 0
alone does not prove every required test ran.

Suggested gate order: relevant pure tests -> real Postgres/RLS/race/fault tests -> full legacy compatibility -> public deterministic + live-model eval -> web/client integration -> ablation/load/recovery -> independent sealed -> authorized pilot/cutover. Do not run expensive suites on every documentation correction; repeat when code/config changes or unresolved failures justify it.

## Release thresholds from V3 (proposed until D09 approved)

| Gate | Required result |
| --- | --- |
| Joint exact + legacy presence | Each >=.95, every named public/sealed seed and required event/fact size; actual delivered facets/provenance/state included |
| Zombie | <=.05 each seed; zero deterministic known stale/invalid current cases |
| Filing | >=.98 over all eligible writes, pending/unassigned counted as misses; no unauthorized/hard near-miss merge |
| Final protected/resolver candidate recall | >=.99, report before/after rerank, each arm and filter stratum |
| Conflict / temporal | >=.90 conflict and >=.95 broad temporal; structured deterministic cases and authorized rollback exactness 100% |
| Ambiguity / abstention | >=.90 ambiguous recall; answerable abstention <=.05; unanswerable correct abstention >=.95 |
| Security / durability | Zero observed leak/injection; zero normal-fault lost acknowledgments; current grants/erasure on history/restore |
| Load / latency | Named workload/hardware and 200 sessions; provisional retrieval+resolver p95 <200ms at 50k, structured ack <=500ms, projection lag <=30s, approved boundary/targets |

Record all denominators, stratum failures, confidence/variance and missing results. Averages never waive a bad seed or deterministic invariant. Targets are not claims, and observed zero attacks is scoped evidence, not proof of impossibility.

For V3, the retained “legacy presence” metric is evaluated against V3's authorized expected set on the new protocol. The untouched old harness additionally reports historical T2/T3/rollback comparisons; its incompatible truth rules cannot be used to force V3 to permit lower-authority overrides, external current or destructive rollback. Compare compatible scenarios directly and publish changed-semantics cases separately with the approved ADR.

## Evidence schema

Each run directory stores a JSON manifest with run ID/time/cwd, exact argument array, interpreter/DB/OS/hardware, git commit plus dirty content hashes, code/harness/oracle/dataset/model/policy/index versions, expected discovered IDs, timeout/failure policy, exit status, counts and sanitized output/CSV/JSON hashes. Include before/after checkpoint evidence, limitations, authorized reviewer and rollback state. Do not retain raw secrets/prompts/personal payloads. A stopped run with no output is NOT_RUN/FAIL, never a measured number.
