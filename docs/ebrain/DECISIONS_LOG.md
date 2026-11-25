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

### M5 voice bridge and M6 T-042 re-run

- `ebrain/voice_client.py` is a client library only. `refresh()` schedules a
  daemon thread and returns immediately; all HTTP work, client construction and
  failures happen on that thread. `pack == ""` until a successful response and
  when no token is configured, so the voice agent runs without memory. The
  real voice agent is not in this repo and `local-voice-assistant` was not
  touched. UNTESTED tags cover real-session freshness and overlapping turns;
  the default 1024 token budget carries a LIMIT note from 08-config.md.
- M6 re-ran T-042 on the **shipped** store (temporary harness adapters outside
  the repo, CSVs in `FINAL/reference/results/t042_shipped_*.csv`). Baseline
  `heal_mode=auto`/join-off vs join-on: 1k seeds 101/102/103 were identical
  (zombie 0.1034 / 0.2167 / 0.250; acc 0.931 / 0.9167 / 0.875). At 10k seed 101
  join-on gave zombie 0.5955 vs 0.5923 and acc 0.6742 vs 0.6758 — no ≥ 0.02
  zombie improvement, and slightly worse. T-042 therefore still fails and
  `subject_join` stays `off`. No measured number in `limits_facts.json` was
  changed; the result is recorded in `FINAL/11-decisions.md` ADR-9.

### M3 UI and spec-test selector correction

- The feature imports `MemoryList` with an explicit `capacityState` prop in
  addition to `client`. 07-ui.md §2.3 shows `<MemoryList client={client} />`,
  but §4c names `capacity_state` as the source of the "beyond tested range"
  per-item badge and `ChainSummary` from `/chains` does not carry it. Passing
  the already-loaded `Limits.capacity_state` avoids a second request and keeps
  every badge sourced from the endpoint; no number is hard-coded.
- The mock client adds synthetic chain/version/pair fixtures and a `heal`
  fixture with one proposal for previewing the M3 drawer and M4 approval UI.
  All copy and measured numbers still come from the copied
  `limits_facts.json`; the new values are preview provenance only, never
  presented as measured.
- **Spec test corrected (selector only):** the supplied M3 test
  `getByText("EXPERIMENTAL")` failed in strict mode because it matched both the
  badge and the endpoint's known-flaw sentence "The experimental same-fact
  detector did not reduce stale values in tests and is OFF." Evidence: the
  Playwright failure listed two matching elements. Changed the locator to
  `getByText("EXPERIMENTAL", { exact: true })`; the assertion is unchanged and
  no test is skipped, removed or made lenient. This follows the M1
  `role="alert"` scoping precedent.

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


### Planner handoff and recoverable workspace consolidation — 2026-11-24

- Owner requested an end-to-end implementation folder and retirement of the
  tournament/offline voice prototype, then explicitly selected V3 as the main
  plan with a crosswalk from the older research handoff milestones.
- `docs/ebrain/implementation-plan/README.md` is the new coding-agent entry
  point: M7–M14, 52 checkpoints, all 30 V3 regression IDs, actual baseline,
  API/architecture/decision contracts, test and migration/recovery procedures.
  V3 product implementation remains NOT STARTED. No architecture/safety/model
  activation or production migration is claimed approved by this log entry.
- The misnamed SPEC_DEV_BRAIN_V2.md contained V3 text and matched the owner's
  Downloads V3 file byte-for-byte. Preserve it as SPEC_DEV_BRAIN_V3.md and
  archive the old filename. Do not invent/reconstruct a true V2 document.
- Preserve 150 frozen spec/reference/harness/research/result files under
  tools/ebrain/legacy with per-file SHA-256. Original competition scaffolding,
  third-party clones, offline app and four loose images are recoverably moved
  to sibling voice-agents-cleanup-backup-20261124 after verified source ZIP.
  Existing application-data DB, API/web product logic and owner work remain.
- Active backend check supplies EBRAIN_FACTS_SOURCES to the unmodified T-024
  test: 72 passed, no skips, one existing Starlette/httpx warning (29.12s).
  Before configuration: 71 passed/1 skipped. Frozen harness: 12 passed (0.55s).
  Separate reference/current-product 1k seed-101 subprocesses reproduce .9310
  presence accuracy and .1207 zombie, zero measured leak/injection/budget/
  crash/ack-loss counts; Python 3.12 runtime and source hashes are recorded.
- Web typecheck, architecture, lint and build passed; 33 selected browser
  tests passed before cleanup and again afterward (41.3s). These are synthetic
  preview checks, not a live owner-authenticated browser/agent validation.
- New wrappers resolve relocated paths and distinguish current product code
  hashes from frozen reference. Frozen evidence and generated limits JSONs
  stay unchanged; no model calls, dependency upgrades, pricing, commits,
  deployments, real-data imports or long-running 50k reruns were performed.
- Exact evidence, owner-file preservation and cleanup manifests live under
  docs/ebrain/implementation-plan/evidence. Live sessions, V3 Postgres/RLS,
  100k distinct facts, 200-session load and V3 quality targets remain NOT RUN.

## 2026-11-25 — V3 implementation decisions (PROPOSED, not owner-approved)

The main-plan selection authorized deterministic implementation and isolated
testing only. The following decisions record choices actually made in code;
they are **PROPOSED** and do not activate production routing, models, pricing,
migration or company deployment. Frozen reference decisions above remain active.

- **D01 (PROPOSED) — isolated V3 backend and schema negotiation.** Added
  `ebrain/v3/` with disabled-by-default flags, strict schema-3 contracts,
  ordered migrations in `migrations/ebrain_v3/0001_init.sql`, and an optional
  psycopg 3 adapter. Legacy SQLite/schema-1 service and tests are untouched.
  No driver/version was added to production pins; psycopg is test-only.
  Evidence: `implementation-plan/evidence/20261125T024900Z-v3integrated/`.
- **D02/D07 (PROPOSED) — model-free resolver, model boundary disabled.** All
  authority, identity and currency decisions use deterministic pure code.
  `models/manifest.py` and `models/classifier.py` validate strict outputs and
  cache by sanitized input; no external/paid model, network call or provider
  was selected. Semantic filing, vector, rerank and NLI flags remain off.
- **D03 (PROPOSED) — authority from admitted grants only.** Admission derives
  authority from server grants; text/lineage cannot raise it. Intended decisions
  and observed states are distinct claim kinds; external/derived evidence never
  establishes current. Conflicts from a shared observed base never use a
  timestamp/UUID tie-break. Legacy lower-authority override stays schema-1 only.
- **D04 (PROPOSED) — typed registry with unknown qualifiers pending.** Required
  qualifiers are never defaulted; units normalize exactly; unsupported
  multi-valued predicates are rejected. Source revisions are immutable and
  deduplicated; partial scans never imply deletion.
- **D05/D08 (PROPOSED) — append-only erasure and separation of duties.** Physical
  history deletion is not used by V3; suppression tombstones and reviewed
  compensating events are appended. Review requires version/digest CAS and an
  independent approver for high-risk changes; absent stewards stay blocked.
- **D06 (PROPOSED) — config-driven fact quotas, separate budgets, price unset.**
  Plan labels are explicitly `unmeasured`; legacy event-count warnings stay in
  schema 1. No currency, price or checkout was invented.
- **D09 (PROPOSED) — independent oracle, joint-exact metric and negative controls.**
  `tools/ebrain/v3-eval/` is test-only, imports no product code, and includes
  protocol/generator/oracle/metrics/runner/manifest plus seven negative controls.
  Sealed suite is NOT_CONFIGURED pending an independent evaluator.
- **D10/D11/D12 (NOT SELECTED / UNSET).** No SSO provider, SCIM delivery,
  production cutover window or price was chosen. Web preview and migration
  tools are rehearsal-only; no live session, deployment or data migration was
  performed.

Full draft ADRs with alternatives, impact, activation and rollback are in
`implementation-plan/evidence/M7/adr-drafts.md`. None of these entries approves
an activation gate; owner approval must be appended as a separate dated record.

## 2026-11-25 — Owner handover approvals (approved policy, local scope only)

Source: owner-approved `OFA E-Brain V3 — Owner Approval & Master Implementation
Handover` (13/13 dispositions). Draft reconciliation: the four M7 drafts in
`implementation-plan/evidence/M7/adr-drafts.md` are consistent with the approved
D01/D03/D09 principles; no material conflict was found. Approval of policy is
not approval of production activation.

- **ADR-D01 (APPROVED).** One atomic PostgreSQL transaction for accepted evidence,
  revision/base state, pending fences, durable outbox, receipt and watermark;
  accepted is not applied. Explicit `X-EBrain-Schema: 3` negotiation with safe
  schema-1 compatibility; unsupported or unsafe representations are rejected,
  never mislabelled current. One authoritative writer during migration; cutover
  requires separate authority. Verified by 22 real-Postgres integration cases
  (`implementation-plan/evidence/20261125T054620Z-pg-integration/manifest.json`).
- **ADR-D03 (APPROVED).** Scoped authority hierarchy: organizational/domain
  decisions > permitted developer assertions > agent suggestions/external
  evidence, within predicate/domain/source contract. Lineage is never permission;
  delegation is explicit and bounded; incomparable authorized branches conflict
  with no scalar current; intended decisions and observed state stay separate.
  T1-T7 are normative. Deliberate divergence from legacy T2/T3 (lower-authority
  override, external current, physical rollback) is retained and versioned:
  legacy tests remain unchanged and V3 cases are separate. Automated routine
  automation is approved for storage/evidence extraction/index refresh/duplicate
  and conflict detection; detection is not approval to merge.
- **ADR-D02/D07 (APPROVED CANDIDATE POLICY, ACTIVATION GATED).** Local AI-assisted
  hybrid retrieval is approved; no paid API, hosted fallback or model authority
  over truth. Approved candidates: `intfloat/multilingual-e5-small` (384) and
  `BAAI/bge-small-en-v1.5` (384) embeddings, `cross-encoder/ms-marco-MiniLM-L6-v2`
  reranker, typed-rules classifier first, optional local Qwen3 4B for hard
  suggestions/summaries, pgvector HNSW only after measured filtered recall.
  Artifact/tokenizer/runtime hashes, calibration and offline proof remain
  pending; no component is active. If none passes, safe exact/lexical with
  explicit degraded status is used.
- **ADR-D08 (APPROVED, LOCAL SINGLE-USER EXCEPTION).** Owner is primary steward;
  backup unassigned. SLAs 4h/24h/72h/7d by priority; timeout escalates and never
  auto-approves. Narrow audited single-user exception is allowed only for
  isolated local development/synthetic tests, never production. High-risk real
  pilot or production operations requiring two distinct humans remain BLOCKED.
- **ADR-D05 (APPROVED LOCAL POLICY).** Retention classes: accepted events for
  project lifetime, cards/embeddings only with eligible facts, receipts 90d,
  debug logs 30d, audit 365d, encrypted backups 30d. Tombstone by default,
  immediate suppression across all paths, controlled hard erasure with
  authorized procedure. Daily encrypted local backups with AES-256 AEAD
  candidate and keys outside the backup; exact key custody/path still owner
  action. Production residency/legal review remains pending.
- **ADR-D06 (APPROVED).** Price is NULL, not zero; billing/paywalls/outbound
  commercial integrations deferred. Usage/resource accounting is allowed;
  monetary cost remains unknown/unmeasured.
- **ADR-D09 (APPROVED PROTOCOL).** Retain all V3 thresholds and per-seed/stratum
  denominators; public 101/102/103 are development only. An isolated OpenCode
  evaluator owns a new sealed suite and commitment; builder cannot read hidden
  labels, seeds or salt. Tuning on a sealed failure retires that suite.
  Isolation, commitment and sealed results remain NOT_CONFIGURED/NOT_RUN.
- **ADR-D10 (DEFERRED).** No live OAuth/OIDC/SCIM, no provider configuration and
  no authenticated production session in this scope. Local server-controlled
  principals + RLS only; preview is never authentication evidence.
- **ADR-D11 (APPROVED FOR REHEARSAL ONLY).** Local migration, backup, restore,
  freeze/fence/delta and rollback rehearsals authorized; real production
  cutover, production DB edits and legacy deletion explicitly deferred.
- **ADR-D12/NOT SELECTED.** No price, provider, hardware target or production
  model artifact is selected by these approvals.
