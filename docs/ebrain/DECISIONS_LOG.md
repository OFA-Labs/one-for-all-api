# E-Brain implementation decisions

## 2026-11-24 — M0 scaffold

- The M0 acceptance command deliberately exits with failing tests. Its required
  result is 52 collected: 22 failed, 6 passed, 1 skipped and 23 errors. The general
  requirement for a green backend suite applies from M1; replacing the stub early
  would violate M0. No test is changed, weakened or newly skipped.
- Copy the reference package, all seven Python test files and requirements
  byte-for-byte. During M0 only, `ebrain/store.py` is the supplied
  `FINAL/reference/m0_store_stub.py`; it raises `NotImplementedError("M1")`.
  The real store and its honesty tags arrive in M1, so T-051 and T-052 remain red
  as specified. Do not add behavior or tags to change this checkpoint.
- `pyproject.toml` repeats all 23 supplied dependency pins and restricts Python
  to 3.12. It uses `tool.uv.package = false`: M0 runs the package from the repo
  root and needs no additional build dependency. Install using the exact
  `requirements.txt` command from the spec.
- The existing backend is a clean README-only checkout; `origin/staging` and
  `main` both start at `67234807075b93ed024005d0da29ad6deaea0c46`.
  Work uses `feat/ebrain-m0`, based on `origin/staging`.
- GitHub reports `OFA-Labs/one-for-all-api` as public. Publishing was initially
  paused because the original instruction required private repos. On 2026-11-24
  the owner explicitly overrode that requirement: keep this repo public and
  publish the contribution PR as `jvsing` to `OFA-Labs`. The GitHub connector
  authenticates as `jvsing`; the CLI authenticates as `OFA-Labs`. Push the feature
  branch using the authorized CLI credentials, create the PR as `jvsing` against
  `OFA-Labs/one-for-all-api:staging`, and leave it unmerged for the owner.
- The web checkout is clean on `feat/icon-navigation-native-engine`; M0 changes
  no web source. Run the requested existing web checks as a baseline using the
  production Playwright server on port 3100. Do not start a development server.
- Existing paths verified before editing: backend `README.md` contains the
  three-line initial description. The frontend `AGENTS.md` has the nine-line
  generated Next.js block described by the spec. Installed Next.js Playwright
  and installation guides were read before web verification.

### M0 validation (2026-11-24)

Commands run from `one-for-all-api`:

| Command | Observed result |
| --- | --- |
| `uv venv --python 3.12 .venv` | Created CPython 3.12.10 environment; exit 0. |
| `uv pip install --python .venv\Scripts\python.exe -r requirements.txt` | 23 pinned packages installed; exit 0. |
| `.venv\Scripts\python.exe -m pytest tests -q` | **22 failed, 6 passed, 1 skipped, 23 errors**, 1 warning, in 8.66s; expected exit 1. |
| `.venv\Scripts\python.exe -m pytest tests --collect-only -q` | **52 tests collected** in 0.75s; exit 0. |

A Python integrity check compared SHA-256 hashes for all 14 copied files
(six package files including the stub, seven test files and requirements).
Every copy matched byte-for-byte. It also compared all 23 requirements with
`pyproject.toml` and installed versions using `importlib.metadata`; all matched.
The one backend warning is the reference's known Starlette/httpx deprecation.
The CSV comparison is the reference's existing skip, not an added skip.

Commands run from `one-for-all-web` (no web implementation in M0):

| Command | Observed result |
| --- | --- |
| `npm run build` | Passed; 22 static pages generated; exit 0. |
| `npx tsc --noEmit` | Passed; exit 0. |
| `npm run lint` | 0 errors, 2 existing warnings in `.cache/motion/patch-duration.mjs`; exit 0. |
| `npm run check:arch` | 0 dependency violations; 87 modules, 180 dependencies; exit 0. |
| `npx playwright test tests/journeys.spec.ts tests/quality.spec.ts` | **17 passed** in 41.4s; exit 0. |

There is no `tests/e-brain.spec.ts` until M1, as specified. The known failing
dictation-hotkey test was not run or modified. Restore generated tracked
screenshots and `next-env.d.ts` before committing. M0 has no working store:
memory writes, queries, isolation, persistence, healing and joins remain
unverified in this port until M1. Frontend memory UI, agent hooks, voice bridge
and the real-port ablation remain future milestones.

## 2026-11-24 — M1 store, API and capacity view

- Start `feat/ebrain-m1` from updated `origin/staging` after the owner merged
  M0 (merge `4bef3f9`). The web branch starts at its latest `origin/staging`
  (`1cd9e73`); its navigation changes are already merged. Both working trees
  were clean before branching. Contributions use `jvsing` forks and target
  OFA-Labs `staging`; the owner performs all merges.
- Port the real reference `store.py` byte-for-byte. Preserve the seven original
  test files, generated facts, dependency pins and safety defaults: self-heal
  `propose`, subject join `off`, capacity soft/hard 800/1000. Add only
  `test_spec_amended` to `tests/test_bridges.py` in M1.
- **Necessary API correction, reproduced before editing:** the reference has
  no CORS middleware. An OPTIONS preflight from `http://127.0.0.1:3100` for
  GET `/v1/ebrain/limits` with Authorization and Content-Type returned HTTP 405
  and no CORS headers. This prevents the spec's browser HTTP client from using
  the separate API port. Add the already-pinned Starlette CORSMiddleware with
  exactly `http://127.0.0.1:3000` and `http://127.0.0.1:3100` allowed, methods
  GET/POST/DELETE and headers Authorization/Content-Type, without cookies or
  wildcard origins. Preflight carries no memory data; actual API operations
  still require a valid bearer token. No other reference API behavior changes.
- Add two CORS regression tests: both local origins and relevant preflight
  methods, authenticated limits, missing-token 401, and rejection of four
  unlisted origins. The full suite therefore has **54 passing tests, 1 skipped**
  rather than the spec's 52 passing tests, 1 skipped. Original tests are neither
  edited nor weakened.
- Web existing-path checks matched the spec: B4.3 is at L283, the existing
  artwork is L11–23, README's placeholder is L72, and the integrations array
  ends at L1249. Read installed Next.js server/client and Playwright guides
  before web edits. Apply the owner-approved B4.3 sentence exactly.
- The web preview imports an additional `src/lib/ebrain/limits-facts.json`,
  copied byte-for-byte from the generated backend facts, instead of retyping
  measured copy and numbers into TypeScript. Preview counts are the spec's
  explicit fixtures; live data comes from `/v1/ebrain/limits`. No measurements
  are changed or invented.
- Keep one client per mounted EBrain using lazy `useState(getEBrainClient)`;
  the limits effect depends on that client. This avoids recreating the client
  on every render and satisfies React's dependency checks without suppressions.
  Requests occur once per mount; cleanup ignores late results.
- Keep the M1 composition and five capacity tests separate from future M3/M4
  UI. Future mock review actions return explicit not-implemented errors; M1
  never claims those controls work. The HTTP seam includes the specified full
  interface; three additional transport tests check bearer identity/project
  selection, HTTP/network failures and human-action request handling.
- Append only blank E-Brain variable names to `.env.example`. Do not inspect
  local environment files or store tokens. README explains that the spec's
  NEXT_PUBLIC token is browser-visible and is for the owner's local setup.
- The owner's requested `j-clone` avatar/name/bio is a separate GitHub identity
  request. The second commit icon is the original One For All co-author, not an
  agent-owned account. Ask for the dedicated account username; do not rename
  the owner's personal `jvsing` profile or rewrite existing commit history.

### M1 backend validation

`.venv\Scripts\python.exe -m pytest tests -q` returned **54 passed, 1 skipped,
1 warning in 3.05s**, exit 0. The skip is the unchanged CSV comparison and the
warning is the known Starlette/httpx deprecation. Thirteen reference-derived
files (including the real store, all seven original tests, facts and pins)
remain byte-for-byte identical; `api.py` differs only for the CORS correction.

The first web capacity run returned 4 passed, 1 failed: Next.js 16's built-in
route announcer also has `role="alert"`, so the supplied unscoped error locator
matches two elements. Scope that assertion to `main` and retain the exact
message check. This is a selector correction, not a behavior change, skip or
weakened assertion.

### Path-chain history correction and final validation

An authenticated write with `path="docs/specs/auth.md"` was accepted and listed
as chain `p:docs/specs/auth.md`, but GET of its percent-encoded history URL
returned HTTP 404 (`Not Found`). Starlette decodes the encoded slash before
matching the original `{chain}` route. Use `{chain:path}` at the same endpoint
and add one regression verifying both version statuses and another tenant's
404. No store, tenancy or replay code changes. This is the second documented
`api.py` deviation from the reference.

The final `.venv\Scripts\python.exe -m pytest tests -q` returned **55 passed,
1 skipped, 1 warning in 4.30s**, exit 0. The three added regression tests explain
the difference from the spec's 52 passes; T-090 is included. The existing CSV
skip and Starlette warning remain unchanged.

Web verification, run from `one-for-all-web`:

| Command | Final observed result |
| --- | --- |
| `npm run build` | Passed; 22 static pages generated. |
| `npx tsc --noEmit` | Passed; exit 0. |
| `npm run lint` | 0 errors, 2 existing cache warnings; exit 0. |
| `npm run check:arch` | 0 violations; 95 modules, 193 dependencies. |
| `npx playwright test tests/e-brain.spec.ts` | **5 passed** in 8.2s after the documented selector correction. |
| `npx playwright test tests/e-brain-client.spec.ts` | **3 passed** in 3.5s. |
| `npx playwright test tests/journeys.spec.ts tests/quality.spec.ts` | **17 passed** in 44.5s, including accessibility and responsive checks. |

An independent integrity check confirms web preview facts, the backend store
and all seven original tests still match the reference byte-for-byte. Restore
generated screenshots and `next-env.d.ts` before each commit. No development
server was started, no local-voice-assistant files were touched, and the known
dictation-hotkey failure was neither run nor changed.

Honest remaining gaps: no real-user accuracy or power-loss measurement; the
configured browser-to-live-API deployment has component/transport/CORS tests
but was not exercised using the owner's real tokens. M2 agent hooks/import,
M3 honesty panels/history UI, M4 approval/pair UI, M5 voice client and M6 real-port
ablation remain future milestones. Subject join stays OFF and healing remains
approval-required.

## 2026-11-24 — M2 CLI and agent bridges

- Both M1 PRs are owner-merged: API `a69e700`, web `5a0b371`. Create clean
  `feat/ebrain-m2` branches from the updated staging refs. Keep the original
  store, facts, dependencies, test files and safety defaults unchanged.
- Verified existing paths before editing: `.claude/settings.json` is the
  six-line attribution object and web `AGENTS.md` is the nine-line generated
  Next.js block. Preserve both and append the M2 configuration/instructions.
- Add `ebrain/__main__.py` as well as `cli.py`: the specified
  `python -m ebrain` command cannot run without a package entry point. Keep
  the existing metadata-only project; no installation/build dependency is added.
- The web working directory cannot import the sibling Python package directly.
  Hook commands explicitly use Windows PowerShell, push into the sibling API
  directory using `CLAUDE_PROJECT_DIR`, run its pinned venv interpreter, and
  restore the original directory. The Codex block gives the same invocation.
  No token values appear in these files or command arguments.
- Read the current official Claude Code hooks reference before configuring
  SessionStart/Stop: JSON input arrives on stdin, plain SessionStart stdout
  provides context, PowerShell requires the environment-qualified project-dir
  variable, and Stop can include an unflushed final assistant message.
  Source: https://code.claude.com/docs/en/hooks.
- **Reproduced bridge mismatch:** a valid plain-text decision is accepted by
  the reference but returns zero query items, because only coded versions
  receive retrieval terms. The CLI adds a deterministic six-character value
  code only when one is absent, retaining explicit codes and the reference
  store unchanged. This adapter mechanism carries an UNTESTED tag for real-note
  slot quality/collision audits, with no real-use reliability claim.
- **Reproduced bootstrap mismatch:** two coded independent facts with the same
  literal `MEMORY.md` path are one chain; querying the first returns the second
  as current. Import therefore uses `<resolved file>#L<line>` source paths
  instead of the spec's bare file path. A regression must verify all three
  imported facts remain queryable. Fenced code is excluded. Entry relocation
  may create new chains; this is tagged UNTESTED rather than silently merged.
- Retain remember's specified op-id formula and current integer timestamp.
  Import/capture use stable source identities and timestamps so an unchanged
  replay is idempotent. Capture processes only assistant text with explicit
  durable markers, not user/tool records. Missing transcript timestamps use
  source creation time if exposed by the OS, otherwise 0 for an undated source.
- Stop skips capture during an active stop-hook continuation. If its final
  marked message is not yet in the transcript, a stable session/text identity
  writes it once; a timestamp-only replay rejection is treated as already seen
  for that fallback alone. A subsequently flushed transcript can still add a
  extra write: the real-session duplication audit remains explicitly UNTESTED.
- The per-request timeout is 2 seconds; hook wrapper deadlines are 10/30
  seconds for start/stop. These are operational bounds, not measured latency
  claims. HTTP uses no environment proxy or redirects; diagnostics redact
  secret patterns and the configured bearer token. No new dependencies.
- Do not import the owner's personal files into an unconfigured real service
  or install permanent placeholder credentials. The two-file bootstrap command
  is documented; integration tests use synthetic Markdown/transcript data and
  isolated temporary stores with synthetic identities. A real personal import
  requires the owner's running API and configured agent token.
- Generated value codes must include the operation identity, not text alone:
  otherwise a legitimate 45 → 30 → 45 change reuses the first code and the
  reference classifies the reversion as a copy instead of a new version.
  Including the stable op_id keeps replay idempotent while allowing reversion
  and avoiding cross-agent origin reuse for independently written equal text.
  Explicit caller-supplied codes are preserved. Add a reversion regression.
- A final scope regression reproduced a false no-op: replaying an unflushed
  Stop message into a second project printed 0 and wrote no row because its
  idempotency key omitted project scope. Include project and visibility in
  import/capture/fallback identities. The new regression must show both
  projects receive their own entry while same-scope retries stay idempotent.
- The exact remember op-id formula intentionally retains second-resolution
  timestamps from the spec. Identical text sent twice in the same second uses
  one id; callers needing distinct same-text operations must use separate
  timestamp seconds. This is not claimed as collision-free operation identity.

### M2 final validation

| Command | Observed result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests -q -k "bridge or bootstrap or codex or claude"` | **11 passed, 55 deselected**, 1 known warning in 58.73s; exit 0. |
| `.venv\Scripts\python.exe -m pytest tests -q` | **65 passed, 1 skipped**, 1 known warning in 73.04s; exit 0. |
| `npm run build` (web) | Passed; 22 static pages generated. |
| `npx tsc --noEmit` (web) | Passed; exit 0. |
| `npm run lint` (web) | 0 errors, 2 existing cache warnings; exit 0. |
| `npm run check:arch` (web) | 0 violations; 95 modules, 193 dependencies. |
| `npx playwright test tests/e-brain.spec.ts tests/e-brain-client.spec.ts tests/journeys.spec.ts tests/quality.spec.ts` (web) | **25 passed (1.1m)**; exit 0. |

The original T-090 assertions remain. Ten new bridge tests cover actual
configured PowerShell commands against an isolated real HTTP API, capture
before maintenance, code reversion, equal-text private/shared origins,
bootstrap of multiple files, code-fence exclusion, independently retrievable
bullets, replay idempotency, private/user isolation, token-budget compliance,
quiet unavailable/unconfigured packs, sanitized failures, rejected writes,
human-route protection and project-scoped Stop fallback.

Regression evidence: text-only generated value codes accepted a 45 → 30 → 45
reversion but left 30 current (the new assertion failed before the identity
seed fix). The project-scope fallback test failed with a false count of 0
before the scope fix, then passed with both project rows present. No reference
test, assertion or skip policy was weakened to obtain these results.

Integrity/syntax checks passed: thirteen reference-derived files, all 23 pins,
merged M1 API code, default heal/join/capacity settings and measured facts are
unchanged. Restore generated web screenshots and `next-env.d.ts` before each
commit. No dev server was started; the known dictation-hotkey failure and old
voice prototype were not touched.

Untested: live Claude/Codex application sessions, personal-file bootstrap with
real credentials, non-Windows hook launchers, real-note import/relocation and
fallback-flush audits, real-use accuracy and power-loss durability. The CLI and
hook commands themselves are integration-tested; this does not claim the
owner's personal service or agent credentials have been configured. M3–M6
remain future milestones. Approval-required healing and join OFF are preserved.

### M2 developer handoff clarification

The owner asked whether the untested work tells the next developer what to do
and what to update after testing. The source already named the unproven
mechanisms and settling tests, but the handoff lacked a consolidated procedure.
Add `docs/ebrain/LIVE_VALIDATION.md` with NOT RUN live checks, pass/fail criteria,
sanitized evidence requirements and instructions for updating comments, logs
and PR descriptions. Link each CLI UNTESTED comment and the README to its
relevant case. This follow-up changes documentation/comments only; no live
session, credential configuration, personal bootstrap or reliability claim is
newly marked tested.
