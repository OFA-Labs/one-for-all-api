# History implementation decisions

Source of truth for the design: `../../../HISTORY_IMPLEMENTATION_PLAN.md` (v2). This file
records what was decided or learned while building the P0 MVP, and where it deviates.

## 2026-11-25 — P0 MVP

### Baselines recorded before any change
- Backend (`pytest tests -q`, Python 3.12.16, pinned `requirements.txt`): **62 passed, 1 skipped,
  3 failed**. The 3 failures are `tests/test_bridges.py::{test_spec_amended, test_claude_hooks,
  test_codex_block}`: they read `../one-for-all-web/AGENTS.md`, a sibling checkout that does not
  exist in this `Jarvis/{frontend,backend}` workspace. They fail before and after History.
- Flaky, pre-existing: `tests/test_store.py::test_two_processes_lose_nothing` (E-Brain) fails about 13%
  of runs (8 of 60 in isolation) because two processes race to open a fresh SQLite database; it imports only
  `ebrain.store`, so it is unrelated to History. A failing full-suite run showing 4 failures instead of 3 is this test.
- Frontend (`npm run verify` steps): typecheck, `check:arch`, lint and `build` pass. Playwright:
  **112 passed, 1 failed**; the failure is `dictation-hotkey.spec.ts:95` and is unrelated.

### Architecture (as planned)
- One combined server `oneforall.api:app` on 8765. E-Brain and History take **separate** config
  dicts (`create_app(ebrain_config, history_config)`) and separate SQLite files; E-Brain code,
  tests, CLI and hooks are untouched.
- The combined app inherits E-Brain's CORS middleware (127.0.0.1:3000/3100, bearer headers, no
  cookies). History does not need it: the browser reaches History through the Next.js proxy.
- History error envelope `{"error": {code, message}}` is installed with handlers scoped to the
  `/v1/tasks` and `/v1/history` prefixes; E-Brain keeps FastAPI's `{"detail": ...}` and `422`.
  Validation errors never echo the rejected input.
- Tenancy by key design: every table is keyed by `(user_id, task_id)`; ids are not global, so
  two users can both hold `sample-pr` and no response can reveal another user's ids.
- Ingest is an upsert keyed by `(user, task_id, revision)` plus a server-side content hash; no
  `X-Idempotency-Key` header. See the README for the full rule table.
- `display_status` is a single Python function with a TypeScript mirror, both tested against the
  same fixture (`tests/fixtures/status_mapping.json` ↔ `frontend/tests/fixtures/status-mapping.json`;
  keep the two copies identical).

### Decisions made while building (not spelled out in the plan)
- **Task ids** must match `^[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}$`. A first test of the proxy showed
  that allowing a leading `.` let `tasks/..` match the route allowlist; ids may not start with
  `.` or `-`. The proxy and backend use the same rule.
- **Links are Tier-A only on the server**, not just in the UI: `result_url` and `evidence.url`
  are `null` unless tier is A and evidence is verified.
- **A "Verified" task must carry an evidence record**; tier D + `verified` is rejected (400).
- **Ingest request body** is read with a streaming 256 KB cap (413) and parsed with
  `model_validate_json`, so oversized bodies are never fully buffered and a bad snapshot's text
  is never echoed.
- **`sqlite3.connect(check_same_thread=False)`**: FastAPI may open a dependency and run the
  endpoint on different worker threads. Each connection is still used by one request at a time.
- **Calendar bucketing is done in Python** (`zoneinfo`) because SQLite cannot convert IANA zones.
- **`tzdata==2026.6` is pinned** (Windows has no system time-zone database).
- **`/healthz`** is public and returns only `ok` plus which store is unavailable.
- **An empty `cursor=`** is treated as "no cursor" (first page).
- **Seed**: the seven records are hard-coded in `history/seed.py` (not imported from the
  frontend). `created_at = occurred_at - block length` so live and preview calendars draw the same
  blocks (jobs 70 min, social 80, decline 20, others 45).

### Frontend decisions
- Live vs preview is resolved **after mount** (`useSyncExternalStore`, server snapshot `null`), so
  the server and first hydration render are a neutral skeleton and no request is made until the
  mode is known. Hydration produces no console errors in either mode (tested).
- The `localStorage` override and `NEXT_PUBLIC_HISTORY_API_URL` accept only same-origin
  `/api/history…` paths.
- The proxy is GET-only with an exact route allowlist, `runtime = "nodejs"`, a 10 s timeout, and
  forwards only `Content-Type` / `Content-Disposition`.
- Local interactive tasks (`/tasks/preview-*`) always use the existing `TaskDetail`, even in live
  mode; they are not stored history.
- The "Today" view tab no longer jumps to the latest sample date; it keeps the current date
  (the "Today" and "Latest activity" buttons do the jumping).
- Preview search keeps matching title + subtitle only (as before); live search also matches the
  goal.
- The home page's "Sample history" card and `browser-history.ts` stay on preview data (out of scope).

### Not built (P1/P2, per the plan)
"All tasks" list view and URL state, `DELETE /v1/history/me` (and its same-origin-checked proxy
handler), `POST /v1/tasks/{id}/events`, artifacts/screenshots and retention, `/events` paging,
facets, FTS5 search, Postgres.
