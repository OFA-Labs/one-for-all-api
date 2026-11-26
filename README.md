# one-for-all-api

Backend for ONE FOR ALL.

The Windows voice companion is documented in [docs/voice/README.md](docs/voice/README.md).

For the current E-Brain baseline and the next coding agent's complete V3 work,
start with the [implementation plan](docs/ebrain/implementation-plan/README.md).
It includes eight milestone READMEs, 52 checkpoints, named regression coverage,
approval gates, migration/recovery and executed validation evidence. V3 is
proposed, not implemented. The retired tournament's frozen spec/harness/results
now live in [tools/ebrain](tools/ebrain/README.md); the obsolete offline voice app
has been archived outside this workspace. The dated M1/M2 notes below describe
the original implementation and do not override the verified current-state plan.

E-Brain is EXPERIMENTAL shared project memory for Claude Code, Codex and the
voice agent. M1 ports the reference SQLite store and authenticated HTTP API:
accepted writes retain their history, queries select admissible current values,
and every read is scoped to the authenticated user and agent's visibility.

Use Python 3.12 and the exact Builder-Ready reference pins:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -q
```

The current pre-plan suite passed **71 tests, with 1 skipped**. This includes the M1
acceptance tests, three M1 integration regressions and ten M2 bridge regressions.
The exact measured-CSV comparison runs when using
`powershell -NoProfile -File tools/ebrain/scripts/Test-CurrentBackend.ps1`, which
supplies the retained CSV paths without changing the original test. Without
that configuration the test may skip. The seven reference test files remain unchanged;
`tests/test_bridges.py` verifies the product-spec amendment, CLI, hooks and
bootstrap, and expects a sibling `one-for-all-web` checkout with PowerShell.

Configure `EBRAIN_TOKENS` outside the repository before using authenticated
routes. It maps bearer tokens to `user`, `agent` and `human` identities; requests
without a recognized token receive HTTP 401. An unset or invalid token map fails
closed. `EBRAIN_DATA_DIR` optionally selects the directory containing
`ebrain.sqlite`; its default is the local application-data directory under
`one-for-all/ebrain`. Never commit real tokens.

Run the service on the local interface only:

```powershell
.venv\Scripts\python.exe -m uvicorn ebrain.api:app --host 127.0.0.1 --port 8765
```

bash (Linux/WSL): `.venv/bin/python -m uvicorn ebrain.api:app --host 127.0.0.1 --port 8765`.
To serve E-Brain **and** History from one process, run `oneforall.api:app` on the same
port instead; see [History](#history-live-mode-p0). `EBRAIN_URL` and the CLI/hooks do not change.

The API exposes `/v1/ebrain/write`, `/v1/ebrain/query` and `/v1/ebrain/limits`,
plus history, human approval/resolution, rollback and delete-my-data routes.
Human authority comes from the token, not a request's claimed identity.
Browser access permits only the local web origins `http://127.0.0.1:3000` and
`http://127.0.0.1:3100`, using bearer headers without cookies. Other origins do
not pass CORS preflight; authentication remains required for API operations.

Every measured capability and limitation is supplied by
`GET /v1/ebrain/limits` from the generated `ebrain/limits_facts.json`; those
measurements use synthetic data, not real-use evidence. Self-heal defaults to
approval required and experimental subject joining defaults to OFF. Above the
tested memory range, bundles carry `beyond_tested_range`. Power-loss durability
and real-agent accuracy remain unmeasured. The web capacity view ships in M1;
the fuller honesty UI, voice client and real-port ablation belong
to later milestones.

Implementation choices and spec discrepancies are recorded in
[the decisions log](docs/ebrain/DECISIONS_LOG.md).

## Agent bridges (M2)

Run the CLI from this directory with the pinned venv interpreter. Configure
`EBRAIN_AGENT_TOKEN` for the intended agent and optionally `EBRAIN_URL` in the
process environment; the default service URL is `http://127.0.0.1:8765`.
The CLI reads no environment files and never takes identity or human authority
from a body field. Use the appropriate agent's token in each agent's process.

```powershell
.venv\Scripts\python.exe -m ebrain pack --text "auth token TTL?" --budget 1024
.venv\Scripts\python.exe -m ebrain remember --kind decision --text "The auth token TTL is 30 minutes."
.venv\Scripts\python.exe -m ebrain capture --transcript C:\path\to\session.jsonl
.venv\Scripts\python.exe -m ebrain maintain
```

`pack` prints the rendered bundle; unavailable or unconfigured memory prints
nothing and exits 0 so work can continue. `remember` prints its acceptance
result; `capture` and `import` print newly accepted entry counts; `maintain`
prints actions. Write/input/authentication failures return a nonzero exit and
a sanitized diagnostic. An unchanged re-import or recapture adds no rows.
Use `--visibility private` for an agent-private note, `--path` for an explicit
source, and `--supersedes ID ...` for an explicit update. Human-only API actions
remain unavailable to agent tokens.

Plain durable text receives a value code if it has none, because the reference
retriever indexes coded versions. Capture accepts assistant text blocks with
`Decision:` or `Remember:` lines; user messages and tool output are excluded.
It does not save the rest of an unmarked conversation. Transcript timestamps
are retained; undated source records use stable file-creation time where
available (otherwise 0, meaning undated). Stop's final-message fallback covers
a record that has not yet reached the transcript. Live transcript layouts and
fallback-versus-flushed duplication remain experimental and require a real
Claude-session audit.

The sibling web repo's `.claude/settings.json` runs pack at SessionStart and
capture followed by maintain at Stop. These hooks explicitly use Windows
PowerShell and this repo's venv, anchored by `CLAUDE_PROJECT_DIR`; they also work
when the web folder path contains spaces. Their JSON stdin and context output
follow the [Claude Code hook contract](https://code.claude.com/docs/en/hooks).
The Codex block in the sibling `AGENTS.md` provides equivalent manual commands.
The two agents still require their own configured tokens and the running API.

## Bootstrap existing Markdown memory

With the API running and the intended agent token configured, run from this repo:

```powershell
.venv\Scripts\python.exe -m ebrain import --file ../one-for-all-web/AGENTS.md --file "$env:USERPROFILE/.claude/projects/c--Users-jaiva-OneDrive-Desktop-voice-agents/memory/MEMORY.md"
```

Import records headings and bullets outside fenced code, without manually
rewriting the source documents. Each source path has a `#L` line anchor so
independent facts in the same file are retained separately. Moving entries to
different lines can create new chains; automatic reconciliation is not enabled.
Environment files, keys and non-Markdown inputs are refused. Synthetic bootstrap
and hook tests use an isolated temporary API/database; they do not initialize or
modify the owner's real database or credentials.

Developer handoff: follow the [live validation checklist](docs/ebrain/LIVE_VALIDATION.md)
for the remaining real-session/bootstrap tests, pass criteria, evidence to
record and the comments/logs to update afterward. Its live checks are NOT RUN;
passing the isolated integration suite does not change that status.

## History (live mode, P0)

History is an owner-scoped, **read-only** view of finished and parked tasks. The browser never
writes it: a future task engine writes snapshots through a service-only endpoint, and a
deterministic seed provides the seven fictional demo records until that engine exists. The
design and decisions are in [`../HISTORY_IMPLEMENTATION_PLAN.md`](../HISTORY_IMPLEMENTATION_PLAN.md)
and [`docs/history/DECISIONS.md`](docs/history/DECISIONS.md).

`oneforall.api:app` is the single local server: it mounts the unchanged E-Brain app plus the
History router (`/v1/tasks`, `/v1/history/*`) and a public `/healthz`. E-Brain and History use
**separate** configuration (`EBRAIN_*` vs `HISTORY_*`) and separate SQLite files.

| Variable | Purpose |
| --- | --- |
| `HISTORY_TOKENS` | JSON map of bearer tokens → `{"user": "<id>", "role": "member"}` (read own history) or `{"user": null, "role": "service"}` (ingest). Unset/invalid → every request is 401 |
| `HISTORY_DATA_DIR` | Directory for `history.sqlite`. Default: `%LOCALAPPDATA%\one-for-all\history` (Windows) or `~/one-for-all/history` |
| `HISTORY_CURSOR_SECRET` | Key that signs pagination cursors. If unset an ephemeral key is used and a warning is logged; set it for anything beyond local development |

Never commit real tokens. The development tokens below are examples only.

PowerShell (Windows):

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt

$env:HISTORY_DATA_DIR = "$env:TEMP\ofa-history"
$env:HISTORY_TOKENS = '{"dev-history-token":{"user":"demo","role":"member"},"task-engine-token":{"user":null,"role":"service"}}'
$env:HISTORY_CURSOR_SECRET = "replace-with-a-long-random-dev-secret"

.venv\Scripts\python.exe -m history.seed --user demo --reset
.venv\Scripts\python.exe -m uvicorn oneforall.api:app --host 127.0.0.1 --port 8765
```

bash (Linux/WSL):

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

export HISTORY_DATA_DIR="${TMPDIR:-/tmp}/ofa-history"
export HISTORY_TOKENS='{"dev-history-token":{"user":"demo","role":"member"},"task-engine-token":{"user":null,"role":"service"}}'
export HISTORY_CURSOR_SECRET="replace-with-a-long-random-dev-secret"

.venv/bin/python -m history.seed --user demo --reset
.venv/bin/python -m uvicorn oneforall.api:app --host 127.0.0.1 --port 8765
```

`python -m history.seed --user <id> [--user <id> ...] [--reset] [--data-dir DIR]` inserts the seven
`is_sample` records through the same validation as the ingest endpoint. It is idempotent;
`--reset` first deletes only that user's demo rows, never real history. It prints counts only.

Smoke test:

```powershell
$h = @{ Authorization = "Bearer dev-history-token" }
Invoke-RestMethod http://127.0.0.1:8765/healthz
Invoke-RestMethod -Headers $h "http://127.0.0.1:8765/v1/tasks?limit=3"
Invoke-RestMethod -Headers $h "http://127.0.0.1:8765/v1/tasks/sample-pr"
Invoke-RestMethod -Headers $h "http://127.0.0.1:8765/v1/history/period?from=2026-11-16&to=2026-11-17&tz=Asia%2FKolkata"
```

```bash
H='Authorization: Bearer dev-history-token'
curl -s http://127.0.0.1:8765/healthz
curl -s -H "$H" 'http://127.0.0.1:8765/v1/tasks?limit=3'
curl -s -H "$H" 'http://127.0.0.1:8765/v1/tasks/sample-pr'
curl -s -H "$H" 'http://127.0.0.1:8765/v1/history/period?from=2026-11-16&to=2026-11-17&tz=Asia%2FKolkata'
```

Endpoints (all JSON, snake_case, `Cache-Control: private, no-store`; errors are
`{"error": {"code", "message"}}`):

| Method | Path | Who | Purpose |
| --- | --- | --- | --- |
| GET | `/healthz` | public | E-Brain + History store check (no details on failure) |
| GET | `/v1/tasks` | member | List with `q`, `status`, `state`, `tier`, `from`, `to` (civil dates, `to` exclusive), `tz`, `sort`, `include_sample`, signed `cursor`, `limit` ≤ 50 |
| GET | `/v1/tasks/{id}` | member | Full read-only record: frozen plan, ordered events, evidence, ledger, approvals |
| GET | `/v1/tasks/{id}/export` | member | The same record as a JSON attachment |
| GET | `/v1/history/period` | member | Every task in a ≤ 42-day range (capped at 500, `truncated` flag) |
| GET | `/v1/history/calendar` | member | Per-day counts in a ≤ 366-day range, bucketed in `tz` |
| POST | `/v1/tasks` | service | Create, replay or revise a snapshot (see below) |

Another user's task id is a `404`, never a `403`. A `member` token cannot write; a `service`
token cannot read. Only Tier A (verified) results ever carry a link, and Tier D never shows as
Verified. Ingest is keyed by `(user, task_id, revision)`: a replay is a no-op; an unfinished task
(`waiting`, `permission`, `question`, `paused`, `unknown`) can advance with a higher revision; a
finished task (`completed`, `declined`, `cancelled`, `error`) is never rewritten, and a revision
may not drop or change an approval.

Tests (the History tests are `tests/test_history_*.py` and `tests/test_oneforall_app.py`):

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

```bash
.venv/bin/python -m pytest tests -q
```

`tests/test_bridges.py` needs a sibling `one-for-all-web` checkout and PowerShell (see the
decisions log); without them its three path-dependent tests fail independently of History.
