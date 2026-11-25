# 01 Architecture

## 1. Shape

```
Claude Code (laptop) ─ hooks + CLI ─┐
Codex (laptop) ─ AGENTS.md + CLI ───┼─> ebrain service: FastAPI 0.165.0 on Python 3.12, 127.0.0.1:8765 ─> SQLite WAL file
Voice backend ─ HTTP session pack ──┤      one Store (one sqlite connection) per HTTP request
one-for-all-web /e-brain (browser) ─┘      user_id + agent_id come only from the bearer token
```

| # | Component | Code (reference = shipped) | Requirement |
|---|---|---|---|
| C1 | Ingest gate: validate, idempotency per (user, op_id), redact secrets, flag injection or spoof | `store.py` `Store.write`, `_validate`, `_gate` | R-002, R-003, R-014 |
| C2 | Chain resolver | `store.py` `_assign_chain` | R-004 |
| C3 | Value registry and lineage | `store.py` `codes` table, `_items` | R-012 |
| C4 | Replay over viewer-visible ops | `store.py` `_chain_ops`, `_evolve` | R-005, R-010 |
| C5 | Retriever (T8 in SQL) | `store.py` `_rank` | R-006 |
| C6 | Packer | `store.py` `_render` | R-009 |
| C7 | Healer (default `propose`) | `store.py` `maintain`, `approve_heal`, `heal_state` | R-030–R-033 |
| C8 | Time machine (tenant-scoped) | `store.py` `query(as_of)`, `rollback(to_ts, project)` | R-007, R-008, R-015 |
| C9 | Capacity guard | `store.py` `memory_count`, `limits`, `capacity_mode` | R-020–R-023 |
| C10 | EXPERIMENTAL subject join (default OFF) | `store.py` `_hybrid_join`, `_trigram_cosine`, `links` | R-040–R-044 |
| C11 | HTTP API | `api.py` `create_app`, module-level `app` | R-023, R-025–R-027, R-060, R-061 |
| C12 | Measured facts for the UI | `facts.py` (generator), `limits_facts.json` | R-024 |
| C13 | Visual brain | one-for-all-web `/e-brain` (07-ui.md) | R-070–R-079 |
| C14 | Agent bridges | `ebrain/cli.py` (M2, specified in 03 §5) | R-080–R-083 |

**No model call and no network call happen on the write or query path (R-013).**

## 2. Where data lives

| Item | Value |
|---|---|
| Brain of record | laptop **directory** `EBRAIN_DATA_DIR` (default `%LOCALAPPDATA%\one-for-all\ebrain`); the file inside it is `ebrain.sqlite` (`store.DB_FILE`) |
| Tenancy | every row carries `user_id`; a `Store` instance is bound to one `user_id` (`Store(path, config, user_id)`) |
| Service | `uvicorn ebrain.api:app --host 127.0.0.1 --port 8765`, run from `one-for-all-api` |
| Threading | FastAPI runs sync routes in a threadpool. Each request opens its own `Store` (dependency `open_store`) and closes it afterwards. No connection is shared across threads. |
| Voice backend on the EU server | calls `POST /v1/ebrain/query` over the user's tunnel. When the laptop is unreachable, the voice agent runs without memory (R-082). There is no replica in this build. |
| Website | never opens SQLite. It calls the API through `src/lib/ebrain/http-client.ts`, or uses the mock client when `NEXT_PUBLIC_EBRAIN_API_URL` is unset. |

## 3. Backend repo layout after M1

The package `new:one-for-all-api/ebrain` sits under `existing:one-for-all-api`, which today holds only `README.md`.

| Path | Origin |
|---|---|
| `new:one-for-all-api/ebrain/__init__.py`, `models.py`, `store.py`, `api.py`, `facts.py`, `limits_facts.json` | copied from `FINAL/reference/impl/ebrain/` |
| `new:one-for-all-api/ebrain/cli.py` | written in M2 (03 §5) |
| `new:one-for-all-api/tests/` | copied from `FINAL/reference/impl/tests/` (7 files: conftest + 6 test files), plus `test_bridges.py` (M2) |
| `new:one-for-all-api/requirements.txt` | copied from `FINAL/reference/requirements-backend.txt` |
| `new:one-for-all-api/.venv` | `uv venv --python 3.12 .venv` then `uv pip install -r requirements.txt` |
