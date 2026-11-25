# E-Brain: Builder-Ready spec (read me first)

**What it is.** A project-memory service shared by Claude Code, Codex and the ONE FOR ALL voice agent, plus a human-readable "visual brain" on the website's `/e-brain` route.

**Base design.** Tournament design **Spec-Y** (versioned fact-chain graph), the judge's provisional leader (`judge/verdict.md`). It is **EXPERIMENTAL**: read `FINAL/HONESTY.md` first. The design is worth using up to about 1,000 memories per project. Even there, sealed synthetic seeds at 1k gave correct_version_acc 0.84–0.95 and zombie_rate 0.08–0.28.

**The reference is the code to ship.** `FINAL/reference/impl/` has the same layout as the backend repo, so files are copied rather than re-typed:

| Reference file | Becomes | Ships? |
|---|---|---|
| `FINAL/reference/impl/ebrain/__init__.py` | `one-for-all-api/ebrain/__init__.py` | copy |
| `FINAL/reference/impl/ebrain/models.py` | `one-for-all-api/ebrain/models.py` | copy |
| `FINAL/reference/impl/ebrain/store.py` | `one-for-all-api/ebrain/store.py` | copy (M1; M0 uses the stub in 10-milestones.md) |
| `FINAL/reference/impl/ebrain/api.py` | `one-for-all-api/ebrain/api.py` | copy |
| `FINAL/reference/impl/ebrain/facts.py` | `one-for-all-api/ebrain/facts.py` | copy |
| `FINAL/reference/impl/ebrain/limits_facts.json` | `one-for-all-api/ebrain/limits_facts.json` | copy (generated; never hand-edit) |
| `FINAL/reference/impl/tests/*.py` (7 files: conftest + 6 test files) | `one-for-all-api/tests/*.py` | copy unchanged |
| `FINAL/reference/requirements-backend.txt` | `one-for-all-api/requirements.txt` | copy |
| `FINAL/reference/m0_store_stub.py` | `one-for-all-api/ebrain/store.py` during M0 only | M0 only |
| `FINAL/reference/impl/adapter.py` | none (benchmark harness glue only) | no |
| `FINAL/reference/variants/`, `FINAL/reference/results/` | none (measurement only) | no |

## Words used in every file

| Term | Meaning |
|---|---|
| MUST / SHOULD / MAY | RFC 2119 |
| memory | one accepted write in one project of one user (12-limits-and-non-goals.md §1) |
| chain | all versions of one fact; **head** = the current version after replaying T1–T7 |
| MEASURED | a number from the frozen benchmark harness on **synthetic** data, with its seeds named |
| ARGUED | reasoning only |

## Build order (10-milestones.md has the dates and exact pass criteria)

| Step | Deliverable | Passing command |
|---|---|---|
| M0 | backend scaffold with the M0 stub store; all tests copied | `cd one-for-all-api; .venv\Scripts\python.exe -m pytest tests -q` gives **6 passed, 1 skipped, 22 failed, 23 errors** (exact red state; see 10) |
| M1 | real store + API; `/e-brain` capacity meter (M1-only composition); SPEC B4.3 amended | backend in `one-for-all-api`: **52 passed, 1 skipped**. The skip is `test_T024_facts_match_measured_csvs`, because the tournament CSVs are not in that repo.; web: `npm run build; npx playwright test tests/e-brain.spec.ts -g "capacity"; npx playwright test tests/journeys.spec.ts tests/quality.spec.ts; npm run check:arch` |
| M2 | `ebrain/cli.py` + Claude Code hooks + Codex block + bootstrap | `python -m pytest tests -q -k "bridge or bootstrap"` |
| M3 | honesty UI (badges, drawer, can/can't, known flaws, heal state, empty/error) | `npx playwright test tests/e-brain.spec.ts` |
| M4 | heal approval UI + pairs UI | Playwright `-g "pairs|heal"` |
| M5 | voice bridge (client library in one-for-all-api) | `cd one-for-all-api; python -m pytest tests -q` |
| M6 | re-run the T-042 ablation | the harness commands in 09 |

## Run the reference (from `c:\Users\jaiva\OneDrive\Desktop\voice-agents\ebrain-tournament`)

| Python | Command | Result (2026-11-23) |
|---|---|---|
| 3.12.10 with the pinned backend deps (the target) | `uv venv --python 3.12 .venv312; uv pip install --python .venv312\Scripts\python.exe -r FINAL\reference\requirements-backend.txt; .venv312\Scripts\python.exe -m pytest FINAL\reference\impl\tests -q -p no:cacheprovider` | **52 passed**, 1 warning (Starlette deprecation of `httpx` in TestClient) |
| 3.11.15 (benchmark venv, stdlib only) | `benchmark\.venv\Scripts\python.exe -m pytest FINAL\reference\impl\tests -q -p no:cacheprovider` | **43 passed, 1 skipped** (`test_api.py` skips: no fastapi) |
| harness | `cd benchmark; .\.venv\Scripts\python.exe -m harness.runner --contender ..\FINAL\reference\impl --size 1000 --seed 101 --out ..\FINAL\reference\results\mine.csv` | see `FINAL/reference/results/RESULTS.md` |
