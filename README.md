# one-for-all-api

Backend for ONE FOR ALL.

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

The full M2 suite passes **65 tests, with 1 skipped**. This includes the M1
acceptance tests, three M1 integration regressions and ten M2 bridge regressions.
The existing CSV comparison skips because benchmark CSVs are not shipped in
this repo. The seven reference test files remain unchanged;
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
