# Current code and verified baseline

Snapshot date: 2026-11-24. Paths below are relative to the workspace unless marked otherwise. [Evidence](evidence/README.md) records commands and results. This inventory describes source inspection and local synthetic checks, not a production audit.

## Existing backend

| Existing path | Responsibility / gap |
| --- | --- |
| `one-for-all-api/ebrain/store.py` | SQLite WAL, `BEGIN IMMEDIATE` writes, user/project scope, append-only writes, fuzzy `_assign_chain`, `_evolve`, ranking/rendering, human heal/pair actions. `rollback` physically deletes rows; `delete_user` removes all user rows. No Postgres, durable fact registry, typed claims, RLS, outbox, bitemporal resolver or enterprise grant layer. |
| `ebrain/api.py` within API | FastAPI, per-request Store, static token map, user/agent derived from token, body human authority downgraded for agent. Local CORS; `/chains/{chain:path}` supports slashes. Legacy response semantics and free capacity fields. No SSO/project grant membership or V3 schemas. |
| `ebrain/models.py` | Legacy dataclasses Write/Query/Item/Trace and a rendered bundle. No V3 accepted/applied receipts or completeness/snapshot contract. |
| `ebrain/cli.py`, `__main__.py` | pack/remember/import/capture/maintain; idempotent synthetic bridge coverage. No MCP adapter. |
| `ebrain/voice_client.py` | Existing uncommitted background HTTP pack client, optional/off when unconfigured. It supplies a pack, not a complete voice runtime. No real-session freshness proof. |
| `ebrain/facts.py`, `limits_facts.json` | Synthetic facts generator + generated UI copy. T-024 can validate exact generated output when all CSV sources are configured. Keep bytes and old measurement definitions until approved new facts schema. |
| `tests/` | Existing API, tenancy, current/historical state, tags, capacities, CORS/paths, facts, CLI/bridge and voice tests. These do not establish V3 team safety. |

Runtime observed: Python **3.12.10** in API venv; Node **v24.16.0**. API pins live in `requirements.txt` and `pyproject.toml`. Do not upgrade unrelated pins during implementation. Legacy research was originally run with Python 3.11.15; relocated reproduction with API Python 3.12 is separately labelled.

## Existing web

`one-for-all-web/src/app/e-brain/page.tsx` mounts `src/features/e-brain/components/e-brain.tsx`. Components include capacity-meter, honesty-panel, memory-list, heal-state, pairs-review, loading/error/empty states and a limits hook. `src/lib/ebrain/` provides schema-1 contracts, HTTP and preview mock clients, and a copied facts JSON.

`client.ts` selects HTTP only when `NEXT_PUBLIC_EBRAIN_API_URL` exists; otherwise it uses mocks. It passes `NEXT_PUBLIC_EBRAIN_TOKEN` into browser code. This is local preview wiring, unsuitable for shared/company deployment; M13/M14 replace it with scoped authenticated sessions and server-held credentials. Current role/onboarding localStorage in Playwright is preview state, not authorization evidence. The HTTP client hardcodes the default project in several methods; M14 must make scope explicit everywhere.

Installed framework: Next.js 16.4.6/React 19.3.1/TypeScript 6.0.3/Playwright 1.65.1 from package lock/config. Before implementing, read `one-for-all-web/AGENTS.md` and installed Next.js guides. Retain unrelated routes/features and media.

## Observed checks during planning

| Check | Observed outcome | Meaning |
| --- | --- | --- |
| Backend before cleanup, `python -m pytest tests -q` | **71 passed, 1 skipped, 1 warning**, 27.14s | Current code differs from handoff’s historical 65. Skip is missing configured CSV sources; warning is existing Starlette/httpx deprecation. |
| Web typecheck | PASS | Existing TypeScript compiles. |
| Web architecture | PASS, 101 modules/210 dependencies, zero violations | Current feature boundaries hold. |
| Web lint | PASS, zero errors/two existing warnings under `.cache/motion` | No new lint error. |
| Web production build | PASS, 22 pages | Local build only. |
| E-Brain client/UI + journeys + quality | **33 passed**, 39.1s | Browser synthetic preview/client tests; no owner token or live service configured. |
| Post-cleanup backend with CSVs configured | **72 passed, 0 skipped, 1 existing warning**, 29.12s | Exact T-024 measured-facts equality now runs; original tests unchanged. |
| Retained frozen harness | **12 passed**, 0.55s | Relocated harness self-tests run successfully. |
| Reference and current-product smoke, 1k/101 | Both accuracy .9310, zombie .1207, zero budget violations/leaks/injection/crashes/ack loss | Separate Python 3.12 subprocesses; legacy synthetic presence metric only. |
| Other post-cleanup checks | See `evidence/current-checks.json` | Records exact observed reruns; never infer from earlier runs. |
| Post-cleanup selected web browser tests | **33 passed**, 41.3s | Synthetic E-Brain/client/journeys/quality checks; same live-session limits. |
| Real Claude/Codex/voice sessions, personal import, power-loss durability | **NOT RUN** | Existing LIVE_VALIDATION.md remains authoritative for these unproven checks. |

## Existing measured research

| Dataset | Shipped legacy presence accuracy | Prototype F presence accuracy | Caveat |
| --- | --- | --- | --- |
| Frozen 1k events, seeds 101/102/103 | .9310/.9167/.8750 | 1.0000/.9500/.8571 | Synthetic; event count is not distinct facts. |
| Frozen 10k events, seeds 101/102/103 | .6758/.6425/.6333 | .8716/.8386/.8468 | F zombie .7544/.7753/.8351; true+stale can score “accurate” in old metric. |
| Extended 50k events, seed 101 | .5006 | .8064 | Different catalogue; F zombie .9192. Auto-cap run stopped, no CSV/no claim. |

All retained raw CSVs live under `one-for-all-api/tools/ebrain/legacy/results/` and frozen reference CSVs under its `FINAL/reference/results/`. These are reported/existing results, not V3 evidence or reruns of every seed during planning. There are no V3 accuracy, 100k distinct-fact, 200-user, cost, latency or real-user accuracy results.

## Dirty owner state

API started with modified `docs/ebrain/DECISIONS_LOG.md` and untracked handoff, misnamed V3 spec, `ebrain/voice_client.py`, `tests/test_voice_client.py`. Web started with five modified E-Brain files and five untracked feature components. Exact status/hashes are in `evidence/git-before.json`. Cleanup preserves these bytes, with the spec filename corrected and the decision log appended separately. Tests may regenerate screenshots/next-env; restore only those known previously clean generated files, never owner changes.
