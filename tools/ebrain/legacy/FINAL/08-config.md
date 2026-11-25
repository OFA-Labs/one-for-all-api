# 08 Config

**Where the keys come from.** Store keys live in `ebrain/store.py` `DEFAULTS`, and `Store(path, config, user_id)` accepts any subset of them. Unknown keys are ignored. `ebrain/api.py` `load_config()` reads `EBRAIN_<KEY upper>` for every key below:
- integer keys are converted with `int`;
- float keys with `float`;
- the rest stay strings.

Every key below is used by the shipped code; no key is unused.

| Key | Env var | Default | Allowed | Used by | Meaning / measured basis |
|---|---|---|---|---|---|
| `capacity_soft` | `EBRAIN_CAPACITY_SOFT` | 800 | int ≥ 1 | `Store.limits` | above: `near_limit` |
| `capacity_hard` | `EBRAIN_CAPACITY_HARD` | 1000 | int ≥ soft | `Store.limits`, `query`, `write` | above: `beyond_tested_range`; sealed 1k acc 0.84–0.95 vs 10k 0.62–0.67 |
| `capacity_mode` | `EBRAIN_CAPACITY_MODE` | `warn` | `warn` \| `reject` | `Store.write` | `reject` → `accepted:false, reason:"capacity exceeded"` when n ≥ hard |
| `heal_mode` | `EBRAIN_HEAL_MODE` | `propose` | `off` \| `propose` \| `auto` | `Store.maintain` | auto harm 0.73–0.83 at 10k |
| `subject_join` | `EBRAIN_SUBJECT_JOIN` | `off` | `off` \| `on` | `Store._assign_chain` | EXPERIMENTAL; no metric change on public seeds |
| `join_auto_threshold` | `EBRAIN_JOIN_AUTO_THRESHOLD` | 0.70 | float 0..1 | `_hybrid_join` | 0.50 was not better |
| `join_review_threshold` | `EBRAIN_JOIN_REVIEW_THRESHOLD` | 0.45 | float < auto | `_hybrid_join` | review precision 0.36 at 10k |
| `join_weight_tokens` | `EBRAIN_JOIN_WEIGHT_TOKENS` | 0.5 | float 0..1 | `_hybrid_join` | not tuned |
| `slot_match_threshold` | `EBRAIN_SLOT_MATCH_THRESHOLD` | 0.45 | float 0..1 | `_assign_chain` | v2 frozen value (first-party join) |
| `slot_match_threshold_external` | `EBRAIN_SLOT_MATCH_THRESHOLD_EXTERNAL` | 0.30 | float 0..1 | `_assign_chain` | v2 frozen value (external join so T3 catches poison) |
| `rank_max_chains` | `EBRAIN_RANK_MAX_CHAINS` | 8 | int 1..32 | `_rank` | query p95 20.6–42.7 ms at 10k (sealed) |
| `snippet_max_tokens` | `EBRAIN_SNIPPET_MAX_TOKENS` | 28 | int ≥ 8 | `_render` | tokens_mean 51 at 1k (sealed) |
| `max_text_chars` | `EBRAIN_MAX_TEXT_CHARS` | 20000 | int ≥ 1 | `_validate` | harness contract |
| `sqlite_synchronous` | `EBRAIN_SQLITE_SYNCHRONOUS` | `NORMAL` | `NORMAL` \| `FULL` (anything else: `ValueError` at Store open) | `Store.__init__` (`PRAGMA synchronous`) | `NORMAL` survives a process kill, not a power cut (06) |
| `default_token_budget` | `EBRAIN_DEFAULT_TOKEN_BUDGET` | 1024 | int ≥ 64 | `api.py` `/query` | used when `token_budget` is omitted |
| `data_dir` | `EBRAIN_DATA_DIR` | `%LOCALAPPDATA%\one-for-all\ebrain` | directory | `api.py` → `Store(path)` | the file is `<data_dir>/ebrain.sqlite` |
| `tokens` | `EBRAIN_TOKENS` | `{}` | JSON object `{"<token>":{"user":"u-jai","agent":"claude","human":false}}` | `api.py` `principal` | unset or invalid → `{}` → every request 401 |

The **removed** keys are `maintain_min_hours` (maintain now runs from the Claude Code Stop hook, 03 §5) and `db_path` (replaced by the `data_dir` directory).

**Bind address and port.** These are not config keys. They are uvicorn arguments: `uvicorn ebrain.api:app --host 127.0.0.1 --port 8765`.

## Other environment variables

| Variable | Used by | Default |
|---|---|---|
| `EBRAIN_URL` | `ebrain/cli.py` (M2) and the voice bridge (M5) | `http://127.0.0.1:8765` |
| `EBRAIN_AGENT_TOKEN` | `ebrain/cli.py`, the voice bridge | required |
| `EBRAIN_TAGS_SRC` | `tests/conftest.py` (optional override of the linted file) | `<ROOT>/ebrain/store.py` |
| `EBRAIN_FACTS_SOURCES` | `tests/test_facts.py` (optional: `results_v2.csv;public_1k.csv;public_10k_101.csv`) | the tournament-relative paths |
| `NEXT_PUBLIC_EBRAIN_API_URL` | one-for-all-web `src/lib/ebrain/client.ts` | unset = mock client |
| `NEXT_PUBLIC_EBRAIN_TOKEN` | one-for-all-web `src/lib/ebrain/client.ts` | `""` |

## Python versions and pins (stated exactly)

| Fact | Value |
|---|---|
| Pins resolved for | **Python 3.12**, with `uv pip compile --python-version 3.12` (uv 0.11.15), into `FINAL/reference/requirements-backend.txt` |
| Direct pins | fastapi 0.165.0, uvicorn 0.54.0, pydantic 2.14.4, starlette 1.10.0, httpx 0.28.1 (TestClient), pytest 9.2.0 (plus 17 transitive pins in the file) |
| Tested on | **Python 3.12.10** (`C:\Users\jaiva\AppData\Local\Programs\Python\Python312\python.exe`), in a uv venv with exactly those pins: **52 passed**, 1 warning (Starlette deprecates `httpx` in TestClient, `StarletteDeprecationWarning`) |
| Also tested on | Python 3.11.15 (the benchmark venv, stdlib only, no pins installed): **43 passed, 1 skipped** (`test_api.py` skips without fastapi) |
| Store dependency | stdlib only (`sqlite3`); `facts.py` is stdlib only |
| Web | no new npm packages |
