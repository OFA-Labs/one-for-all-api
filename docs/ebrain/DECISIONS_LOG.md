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
