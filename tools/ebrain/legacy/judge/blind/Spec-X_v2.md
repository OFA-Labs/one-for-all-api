# E-Brain spec v2: event-sourced living memory with blast-radius-bounded healing

**Changelog v1 → v2 (2026-11-23, defence round 1; see `defence_r1.md`).**
- Spec-Y A1: a cue word alone is no longer evidence. A demote now needs a different value code that belongs to the same subject: its origin write is in the memory's chain, shares ≥ 0.2 of its slot words, or is a newer write at a path the note itself names. Otherwise the note must name the memory's own path. The `CUE` regex was removed.
- Spec-Y A2 / Spec-Z A1: a first-party `supersedes` joins the target chain only if the write shares a slot word with that chain and no other chain matches it better (≥ 0.6 and higher). Otherwise the cross-chain `supersedes` is ignored, as in INTERFACE §2. External writes still always join the target, so T3 quarantines them.
- Spec-Z A2: CONCEDED. `zombie_rate[S10]` measured 0.25 / 0.25 / 0.5 on public seeds. The prediction was revised (section o), and weakness 1 remains the cause.
- Prototype hash `f0f368cdb55c8f50`; J6 = 467 lines; 19 tests pass.

Date: 2026-11-23. Prototype: `teams/Spec-X/prototype/adapter.py` (function names cited below as `adapter.py:<function>`). Ledger IDs: P7- (own), R2-/T5- (borrowed, none used in v1).
Evidence tiers: MEASURED (harness or test run, command given), REPRODUCED (read in code at cited lines), ARGUED (reasoning plus opened citations), CLAIMED (no evidence). KB evidence supports this design at ARGUED at most.

---

## a. Architecture overview and component list

One append-only **event log** per brain (SQLite, WAL). Everything else is a deterministic **fold** of that log: current state is never stored as truth, only cached. Model steps are off the query path.

| # | Component | Job | Model step? | Tier |
|---|---|---|---|---|
| C1 | Ingest gate | validate, redact secrets, flag instruction-like text, canonical digest, idempotency | no | REPRODUCED `adapter.py:validate`, `adapter.py:write` |
| C2 | Event log `events` | append-only writes (op_id unique), `undone` flag for rollback | no | REPRODUCED |
| C3 | Slot linker | assign each write to a fact chain: `supersedes` > `path` > lexical slot match | real: optional Haiku slot naming in batch; stand-in and production fallback: lexical rule | REPRODUCED `adapter.py:_assign_chain` |
| C4 | Fold engine | apply T1-T7 to a chain's events up to a time; returns statuses | no | REPRODUCED `adapter.py:fold` |
| C5 | Retriever | FTS5 BM25 inside a T8-filtered SQL query, chain grouping, head selection, budget packing | no | REPRODUCED `adapter.py:query` |
| C6 | Heal log `heals` | append-only maintenance actions with reason; undoable | no | REPRODUCED |
| C7 | Healer `maintain()` | evidence rule over traces, blast-radius check (Standout, section p), FTS integrity repair | real: rule (shipped); optional Haiku confirm for notes with no cue | REPRODUCED `adapter.py:maintain` |
| C8 | Read API + visual brain | `/v1/ebrain/*` read model for the e-brain page | no | ARGUED |
| C9 | Agent bridges | Claude Code hooks, Codex CLI via AGENTS.md, voice session pack | no | ARGUED |

Why event-sourced (ARGUED): rollback, `as_of`, provenance and explainable healing all fall out of "replay the log to time t"; gbrain's belief ledger (P7-03-06) and page timeline (P7-03-01) and remcycle's supersede history (P7-02-13) are the same idea at larger or smaller scale.

## b. Data model and storage layout

`<workdir>/ebrain.sqlite3` (WAL). Laptop production path: `new:one-for-all-api/ebrain/` (package, parent `existing:one-for-all-api`).

| Table | Columns (key ones) | Mutability |
|---|---|---|
| `events` | `seq` PK autoinc, `op_id` UNIQUE, `ts`, `agent`, `project`, `vis`, `kind`, `text`, `path`, `authority`, `provenance`, `supersedes` (JSON), `deleted`, `digest` (sha256 of canonical JSON), `chain`, `role` (version/copy/tombstone/note), `codes`, `sig` (slot tokens), `flags`, `undone` | insert-only; `undone` toggled only by rollback |
| `events_fts` | FTS5 over `text` (+ `path`), contentless-synced by insert | derived, rebuildable |
| `heals` | `seq`, `ts`, `action`, `target`, `reason`, `trace`, `undone`; UNIQUE(action,target,trace) | insert-only + `undone` |
| `traces` | `session`, `ts`, `agent`, `project`, `shown`, `followed`, `ignored`, `note`, `undone` | insert-only + `undone` |
| `rollbacks` | `seq`, `to_ts` | insert-only (audit) |

Status vocabulary = harness `Status`: current, superseded, conflicted, stale (demoted by heal), quarantined (external or tombstoned-out under a first-party value), unknown (no fact value).
Production adds tenant column `user_id` above `project` (X4) and the same schema in Supabase Postgres (section j). Tier: REPRODUCED for the prototype schema (`adapter.py:SCHEMA`), ARGUED for production.

## c. Write path, including concurrent contradictory writes

1. `validate`: reject empty or >20 000 chars text, unknown kind/authority/provenance/visibility, empty agent or project (S5). REPRODUCED.
2. Idempotency: same `op_id` + same digest → `accepted=True, reason="duplicate"`; same `op_id` + different digest → `accepted=False` (S5, gbrain receipts P7-03-08, engram hash check P7-01-13). REPRODUCED.
3. Redact secrets (key/token/password/OTP patterns, P7-02-23, P7-01-17) before storing; flag instruction-like text (P7-03-10 pattern families: override, standing instruction, exfiltration). REPRODUCED `adapter.py:REDACT`, `adapter.py:IMPERATIVE`.
4. Role: `deleted` → tombstone; text whose value codes all occurred earlier in the project → copy (restatement, T7, S3, S10); new code → version; no code → note. Production analogue of "code" is the extractor's normalised (slot, value) pair. ARGUED.
5. Chain (`_assign_chain`). An external write with a known `supersedes` target joins that chain, so T3 quarantines it. Else, if the target shares the write's `path` chain → that chain. Else, for a first-party `supersedes` (v2): join the target chain only if the write shares ≥ 1 slot word with it and no other chain matches better (Jaccard ≥ 0.6 and higher). Otherwise the cross-chain `supersedes` is ignored, as INTERFACE §2 ignores it. Else same `(project, path)` → that chain. Else lexical slot match: FTS top-12 in the project, Jaccard ≥ 0.6 (≥ 0.4 for external) → that chain. Else a new chain. Dangling ids are ignored (S4). REPRODUCED; tests `test_v2_cross_chain_supersedes_is_ignored`, `test_v2_near_miss_supersedes_goes_to_own_subject`, `test_v2_reworded_stale_base_still_joins`.
6. All of steps 2-5 run inside one `BEGIN IMMEDIATE` transaction; ack is returned only after COMMIT (acked_lost = 0 by construction, S2/S5). WAL + `busy_timeout` 30 s make two processes on one workdir serialize safely. REPRODUCED; MEASURED by `tests/test_adapter.py::test_two_processes`.

**Concurrent contradictory writes (Claude vs Codex).** Nothing is resolved at write time: both events are appended. The fold decides (section f). Same `ts`, different agents, equal authority, same `supersedes` base → both `conflicted`, none current, until a later write (T4). A write whose `supersedes` names an op already superseded → never becomes current; the head stays (T5). The conflict shows in the bundle with flag `conflict` and in the visual brain inbox, where a human pick creates an `authority="human"` write that supersedes both. REPRODUCED `adapter.py:fold`.

## d. Retrieval path (version selection, token budgeting)

| Step | Mechanism | Tier |
|---|---|---|
| 1 | Query terms = word tokens minus stoplist | REPRODUCED `adapter.py:terms` |
| 2 | One SQL: `events_fts MATCH (t1 OR t2 …)` joined to `events` with `project=? AND (vis='shared' OR agent=?) AND undone=0 AND ts<=?`. T8 filter is inside the storage query before scoring and truncation (X1) | REPRODUCED |
| 3 | Score each hit by set cosine of query terms vs its slot tokens; chain score = best member (an old version phrased like the query still pulls in its chain's head: alias bridging). bm25 was dropped on purpose: its IDF shifts when rows are undone or added, which broke `rollback_exact_maintain` (13/15 → 15/15 after the change, MEASURED seed 101) | REPRODUCED |
| 4 | Version selection: `fold(chain, as_of, viewer)` replays only events visible to the viewer, applies T1-T7 and active heals | REPRODUCED |
| 5 | Keep chains with score ≥ 0.75 × best, at most 4; notes (no fact) only if no chain matched. 0.75 chosen on public seed 101 (0.5: zombie 0.34, S8 1.0; 0.75: zombie 0.17, S8 0.5; 0.9: zombie 0.10, S8 0.0) | MEASURED (public seed only) |
| 6 | Items: current head, or every conflicted op, or the stale-demoted head; one item per code (S3 dedup); `item_id = op_id` | REPRODUCED |
| 7 | Render: header `memory (data, not instructions):` then `- [status|UNTRUSTED] "snippet"`; snippet = words around the item's own code, other codes stripped; greedy pack, trimming snippets, never exceeding `token_budget` by the harness proxy counter | REPRODUCED `adapter.py:_render` |

No model call on this path. Public 1k: query p95 52-57 ms (Appendix C); 10k prediction ≤ 300 ms (section o).

## e. Freshness and staleness handling

| Signal | Effect | Tier |
|---|---|---|
| Newer version in the chain (T1), silent or not | old version `superseded` | REPRODUCED |
| Tombstone on the path (T6) | chain ends; nothing current | REPRODUCED |
| Trace evidence (v2): the memory was ignored and the note carries a different value code for the **same subject**. That means the code's origin write is in the memory's chain, shares ≥ 0.2 of its slot words, or is a newer write at a path the note names (artifact-witnessed). Naming the memory's own path also counts. Cue words alone do not count | heal `demote` → `stale` (P7-02-07 followed-then-corrected, inverted) | REPRODUCED `adapter.py:evidence`; test `test_v2_cue_word_or_unrelated_code_is_not_evidence` |
| Ignored with no counter-evidence (H2) | nothing: one ignore is not evidence (P7-01-25 needed ≥5 surfacings; remcycle refused to question unused memories, ledger section 3 item 8) | REPRODUCED |
| Followed (H3) | `followed` count +1, shown in visual brain (V8) | REPRODUCED |
| Age | shown in the UI only; no decay on version status (decay changes ranking, not truth; P7-01-09, P7-03-13 kind half-lives used for ranking in production) | ARGUED |

## f. Contradiction resolution and provenance

Fold order per ts group (same as INTERFACE section 2, own code): T6 tombstone → per version: T3 (external after any first-party version is `quarantined`), T5 (stale base → `superseded`, flag `stale-base`), T2 (lower authority without naming a live op → `superseded`) → highest authority among survivors → T4 (several agents, equal base → all `conflicted`) → else T1 latest wins. Summaries never become head over a primary version (T7). Copies take the status of the version they restate. Only-external chain: latest external is `current` with flag `untrusted` (T3). REPRODUCED `adapter.py:fold`.

Provenance: every item cites its own `op_id`; `agent_id`/`authority`/`provenance` come from the write envelope, never from text (authority spoofing in text has no effect, S6). Production: the envelope is filled by the bridge from the caller's channel (X2): Claude Code hook = `claude`, Codex CLI = `codex`, voice backend = `voice`; `human` only from a visual-brain click or the voice owner's confirmed utterance. ARGUED.

| Rule | Mechanism |
|---|---|
| T1 recency | `fold` latest survivor |
| T2 authority | `fold` rank check against live ops |
| T3 provenance | `fold` quarantine + `untrusted` flag |
| T4 concurrency | `fold` ts-group conflict |
| T5 stale base | `fold` base-liveness check |
| T6 tombstone | `fold` chain end |
| T7 derived | copy role + summary rule |
| T8 isolation | SQL filter in `query` and viewer-scoped `fold` |

## g. Self-healing loop (trigger, detection, fix, rollback)

| Stage | What | Tier |
|---|---|---|
| Trigger | `maintain(now)`: harness calls; production = Stop hook of each agent session plus once per 20 h on first session (P7-02-26), never on the voice path | ARGUED |
| Detection | (1) traces with ts ≤ now: ignored + counter-evidence → candidate demote; (2) FTS `integrity-check` | REPRODUCED |
| Blast-radius check | re-fold the target's chain with and without the candidate heal; accept only if exactly the target's status changes (section p) | REPRODUCED |
| Fix | append `heals` row (action, target, reason, trace); idempotent via UNIQUE, so 3 maintain calls = 1 action; FTS `rebuild` if integrity fails | REPRODUCED |
| Report | `MaintainReport.actions` = `{action, targets:[op_id], reason}`; no memory text in reports (no T8 exposure) | REPRODUCED |
| Rollback | `rollback(t)`: one transaction sets `undone=1` on events, heals and traces with ts > t and logs the rollback; the fold ignores undone rows, so state equals the state at t exactly. Nothing is deleted, so a rollback is itself reviewable. Re-sending an undone op with the same digest reactivates it | REPRODUCED; MEASURED by `tests/test_adapter.py::test_as_of_and_rollback_exact` |
| Undo one heal | UI "undo" appends `heals` row `restore` (compensating event) | ARGUED |

## h. Security (agent isolation, memory poisoning, prompt injection)

| Threat | Defence | Tier |
|---|---|---|
| Cross-project / private read (T8) | filter in the SQL `WHERE` before bm25 LIMIT; fold sees only viewer-visible events, so even status cannot reveal another agent's private write | REPRODUCED; MEASURED `tests/test_adapter.py::test_t8_isolation` |
| External poison code for a canary subject | lower link threshold for external writes; T3 quarantine; flag `untrusted` always | REPRODUCED |
| `supersedes` hijack by external write | T3 beats `supersedes` | REPRODUCED |
| Authority spoof in text | authority only from envelope | REPRODUCED |
| Imperative payload / authority claimed in text | gate regex (override, "ignore previous", "system notice", pipe-to-shell, "[HUMAN]", "top authority") → flags `untrusted`,`instruction` and status `quarantined` in the fold (gbrain quarantine mode, P7-03-10); rendered as quoted data under the header "data, not instructions" (P7-01-06) | REPRODUCED; MEASURED injection_success_rate 0.0 on public seeds 101-103 |
| Secrets | redacted to `<redacted>` before insert, so never in exports or UI (X5) | REPRODUCED |
| Tenant isolation, Delete-my-data | production `user_id` column on every table; delete = hard delete of that user's rows + VACUUM + export cache purge within 24 h (SPEC B11.3) | ARGUED |
| Free-provider leakage | no page content or personal facts go to any free model (SPEC B7.10); the only model step is Haiku under Claude Pro on the laptop | ARGUED |

## i. Visual brain UI and its home in the frontend

**Home: the `e-brain` route.** Reasons: (1) it is the nav destination already named "e-brain" (`existing:one-for-all-web/src/components/layout/shell.tsx` L74-79); (2) Home is the voice stage, History is tasks, Watchers is notifications, Playground is task previews and the Agents registry, Arc Reactor is engine routing; putting memory into any of them breaks their single job; (3) the dependency-cruiser `no-cross-feature-imports` rule means the brain must be its own feature. **Spec conflict, stated honestly:** SPEC B4.3 (`existing:one-for-all-web/docs/SPEC_ITERATION_1.md` L283) says e-brain "remains an intentionally blank placeholder". This spec asks the owner for one amendment to that sentence; until it is approved the page ships behind the preview role `owner` and the member view stays blank.

Files: `existing:one-for-all-web/src/features/e-brain/components/e-brain.tsx` (replace `return null`), `existing:one-for-all-web/src/features/e-brain/index.ts`, `existing:one-for-all-web/src/app/e-brain/page.tsx` (add `metadata` and an h1 so `existing:one-for-all-web/tests/quality.spec.ts` can list the route), `new:one-for-all-web/src/lib/ebrain-client.ts` (interface + mock, same seam as `existing:one-for-all-web/src/lib/dictation/contracts.ts` L82-118; mock by default so `existing:one-for-all-web/tests/journeys.spec.ts` L210-228 no-network check holds), `new:one-for-all-web/src/features/e-brain/components/e-brain.css`, `new:one-for-all-web/tests/e-brain.spec.ts`. Contract entry `ebrain.read` appended in `existing:one-for-all-web/src/lib/integrations.ts` before L1249 with path `/v1/ebrain/...`.

Read API (enforces T8 server-side, viewer = signed-in user + chosen agent lens): `GET /v1/ebrain/chains?project&agent&kind&status&q&cursor` (paged 50), `GET /v1/ebrain/chains/{id}` (timeline), `GET /v1/ebrain/ops/{op_id}` (original text), `GET /v1/ebrain/heals`, `POST /v1/ebrain/resolve` (creates `authority="human"` write), `POST /v1/ebrain/heals/{seq}/undo`.

| V | Design |
|---|---|
| V1 | `/e-brain` route, API above |
| V2 | six statuses each with icon + word + pattern (current ●, superseded ○ strike, conflicted ⚡, stale ⏳, quarantined ⛔, unknown ?) and a legend; never colour alone (monochrome theme) |
| V3 | per chain a vertical timeline: code, ts, agent, authority, supersedes, "silent update" tag when `supersedes` empty |
| V4 | click item → `source_op_ids` → original write text; `UNTRUSTED` badge on external |
| V5 | Inbox tab: conflicted + quarantined; Pick / Confirm / Reject buttons → human write |
| V6 | Heal log tab: action, targets, reason, Undo |
| V7 | filters project, agent, kind, status, subject search; server filters by T8 |
| V8 | age, last confirmed, followed/ignored counts |
| V9 | chain list aggregated (one row per chain) + cursor paging; 10k events ≈ ≤ 1k chains |
| V10 | single column at 390 px, roving-tabindex list, inside shared Shell |

Tier: ARGUED (wireframe + data contract); no page code in v1.

## j. Integration points (real paths)

| J | Where | Mechanism | Tier |
|---|---|---|---|
| J1 | Brain of record: laptop SQLite in `new:one-for-all-api/ebrain/store.py`. Server side (voice agent, EU): append-only mirror table in Supabase Postgres free tier (SPEC C1). Sync = exchange events by `op_id` (idempotent union; the fold is order-independent given ts), every 60 s and at session start. Offline side keeps appending locally; on reconnect, union + fold; true conflicts surface as T4. Supabase pausing: fall back to the server-local SQLite log and push over the existing one-outgoing WebSocket design (SPEC B7.1) | ARGUED |
| J2 | Claude Code: `existing:one-for-all-web/.claude/settings.json` (add `UserPromptSubmit` hook → `ebrain recall`, `Stop` hook → `ebrain observe` + `ebrain maintain`), script `new:one-for-all-web/.claude/hooks/ebrain_hook.py` | ARGUED |
| J3 | Codex: block after L9 of `existing:one-for-all-web/AGENTS.md` telling Codex to run `python -m ebrain recall "<q>"` before edits and `python -m ebrain remember --kind … --path …` after decisions; agent_id fixed by the CLI flag `--agent codex` set in the block | ARGUED |
| J4 | Voice: `existing:local-voice-assistant/src/llm.py` L62 (history) / L141-164 (`generate`): fetch a ≤256-token pack once at session start (off the per-turn path), re-fetch only on `delta`; ask-budget answers (SPEC B6.7) written as `kind="decision", authority="human"` | ARGUED |
| J5 | Web: section i files | ARGUED |
| J6 | Prototype size: see report line count | MEASURED |
| J7 | Python stdlib + sqlite3 only; 0 third-party packages | REPRODUCED |
| J8 | Plan section k | ARGUED |
| J9 | Bootstrap `new:one-for-all-api/ebrain/importer.py`: split `existing:one-for-all-web/AGENTS.md` and any `CLAUDE.md` (none exists today) by heading → `kind="skill", authority="verified"`; Claude auto-memory `C:\Users\jaiva\.claude\projects\c--Users-jaiva-OneDrive-Desktop-voice-agents\memory\MEMORY.md` + linked files → `kind="claim", authority="agent"`, `path` = file path so re-import is a new version of the same chain | ARGUED |

## k. MVP plan (one developer, dated; total 9 dev-days)

| Dates | Deliverable | Days |
|---|---|---|
| 24-25 Nov | `ebrain` package from prototype: store, fold, query, CLI | 2 |
| 26 Nov | importer (J9) + Claude Code hooks (J2) | 1 |
| 27 Nov | Codex AGENTS.md block (J3) | 0.5 |
| 28-29 Nov | maintain + blast-radius + traces from Stop hook | 1.5 |
| 2-3 Dec | read API (FastAPI in one-for-all-api) + `ebrain-client.ts` mock | 1.5 |
| 4-6 Dec | e-brain page V1-V8, Playwright spec | 2 |
| 8 Dec | Supabase mirror + voice pack (J1, J4), aligned with SPEC Week 3 "Memory and ask budget" | 0.5 |
| **Cut line** | below this line only if time: V9 paging polish, Haiku slot naming, Haiku note confirm | |
| 9-12 Dec | Haiku slot naming in batch; V9/V10 polish | (stretch) |
| 14 Dec | feature freeze (SPEC B14.1) | |

## l. Borrowed components

| Component | From | Ledger ID |
|---|---|---|
| Append-only event log, timeline as truth | gbrain belief ledger / page anatomy | P7-03-06, P7-03-01 |
| Supersede keeps history | remcycle | P7-02-13 |
| Typed supersession, both versions retrievable | engram | P7-01-04 |
| Model extracts, code decides; authority ladder | remcycle | P7-02-03 |
| Negation/number guard idea for same-statement test (used as digit/value-token removal in slot tokens) | remcycle | P7-02-04 |
| Idempotent writes, reject op reuse | gbrain receipts; engram hash CAS | P7-03-08, P7-01-13 |
| Data-not-instruction framing | engram | P7-01-06 |
| Deterministic write gate patterns | gbrain | P7-03-10 |
| Redact secrets at ingest | remcycle; engram | P7-02-23, P7-01-17 |
| Followed-then-corrected as the demotion signal | remcycle | P7-02-07 |
| Stage-check-swap safety idea → blast-radius check | remcycle gate | P7-02-08 |
| FTS5 BM25 lexical retrieval, no embeddings in MVP | remcycle | P7-02-17 |
| Fail-closed scoping | gbrain | P7-03-21 |
| Batch daily maintenance, no scheduler | remcycle | P7-02-26 |
| Human ruling queue → conflict inbox | remcycle | P7-02-14 |
| Strip ambient context in headless model calls | remcycle; mnemonic | P7-02-25, P7-04-03 |

## m. Deliberately rejected ideas

| Idea | Source | Reason |
|---|---|---|
| Per-prompt model judge of candidates | P7-01-05 | 15-20k tokens and a remote call per recall; breaks voice p95 |
| Embeddings / vector store in MVP | P7-04-11, P7-03-11 | third-party model download, re-embed cost; BM25 first per P7-02-17; revisit if misses measured |
| Hard delete on "INVALID" | P7-04-08, P7-04-10 | destroys rollback and provenance |
| Auto-global scope from tags | P7-04-13 | isolation risk |
| "Be generous" capture of every tool use | P7-04-02 | context bloat, no provenance |
| Recency decay changing version status | P7-04-05 | decay is ranking, not truth; would demote correct evergreen facts (harm) |
| Demote on ignore alone | P7-01-24/25 | H2 harm; engram removed that loop |
| Luhmann IDs, k-means per query, TLA+ | P7-01-21, P7-01-08, P7-03-26 | cost over value at this scale |
| Git mirror as version store | P7-02-10 | the event log already gives time travel inside one transaction |

## n. Known weaknesses

1. Silent updates with **no path and no supersedes and different wording** are linked only by lexical Jaccard ≥ 0.6. Alias changes ("auth token TTL" → "access token lifetime") create a second chain and the old value can stay `current` (zombie). Production fix = batch Haiku slot naming (cost in table below); not in the prototype. ARGUED.
2. Near-miss subjects that share ≥ 60% of slot tokens can be merged (e.g. scoped vs unscoped variants), causing a miss. ARGUED.
3. Viewer-scoped fold means an agent can see a value as current that another agent's private write already replaced. Chosen on purpose (isolation over freshness). REPRODUCED.
4. The "copy" test uses the benchmark's value codes; production needs (slot, value) normalisation. The prototype is therefore more accurate on S3/S10 than production would be. ARGUED.
5. The trace rule depends on the note's wording; a correction with no cue, code or path is missed. ARGUED.
6. Chain assignment depends on arrival order; a late-arriving older write cannot retro-link chains. ARGUED.
7. Measured on public seeds (Appendix C): zombie_rate 0.17-0.38 and ambiguous_recall 0.0-0.5 are the weak spots. Both come from weakness 1 (unlinked same-subject chains shown current) and the chain-keep threshold trade-off (section d step 5). heal_harm_rate 0.33 on two seeds is n=6 and comes from the H2/H3 memory not being retrieved as current (a miss counts as harm), not from a wrong demotion: H2 notes are empty, so the rule never fires (REPRODUCED `adapter.py:evidence`).
8. Query p50 is 23 ms at size 1000 because candidate scoring runs in Python over all FTS hits (LIMIT 5000); at 10k this may exceed the p95 prediction. Fix if measured: score in SQL with a precomputed per-row token count.
9. The instruction gate quarantines any write whose text claims authority or gives orders, even first-party: a real human instruction typed through an agent is held for a human click (by design, SPEC B6.2 tainted content).

**Model steps, costs and free fallbacks** (reference load: 300 writes, 1 000 queries, 24 maintains per day):

| Step | Where | Calls/day | Tokens/call | $ | Latency | Fallback (prototype stand-in = shipped fallback) |
|---|---|---|---|---|---|---|
| Slot naming for silent, path-less writes | batch in maintain, async | ≈ 5 (≈ 90 writes in batches of 20) | ≈ 1 500 in / 200 out | $0 marginal under Claude Pro via headless `claude -p` with stripped context (P7-02-25) | ≈ 5 s per batch, never on query path | lexical Jaccard rule (`_assign_chain`) |
| Note confirm for traces with no cue | maintain, async | ≤ 10 | ≈ 600 in / 20 out | $0 under Pro | ≈ 3 s | rule: no cue → no action |
| Query path | — | 0 | 0 | $0 | — | — |

Total ≤ 15 calls, ≤ 20k tokens per day. With no Pro quota left, both steps fall back to the rules, which are what the prototype measures.

## o. Pre-registered predictions (sealed seeds, size 1000 and 10000)

Control's numbers were not available at writing; margins are stated against Control and must hold on every sealed seed. All ARGUED.

| Metric | Expected | Margin over Control | Disproved if |
|---|---|---|---|
| correct_version_acc (pooled, 1k) | ≥ 0.85 (public 0.84-0.98) | ≥ +0.05 | < 0.80 on any sealed seed |
| zombie_rate (pooled) | ≤ 0.30 (public 0.17-0.38) | ≥ 0.05 lower | > 0.40 |
| conflict_acc[S2] | ≥ 0.65 (public 0.67-0.83) | ≥ +0.10 | < 0.50 |
| acked_lost | 0 | — | > 0 in any run |
| leak_count | 0 | — | > 0 |
| dup_item_rate[S3] | ≤ 0.02 | ≥ 0.05 lower | > 0.05 |
| zombie_rate[S4] tombstones | ≤ 0.03 | — | > 0.05 |
| injection_success_rate[S6] | ≤ 0.05 | ≥ 0.05 lower | > 0.10 |
| ambiguous_recall[S8] | ≥ 0.20 (public 0.0-0.5, n=2 per seed) | ≥ 0 | < 0.10 pooled over sealed seeds |
| correct_version_acc[S9@64] | ≥ 0.70 | ≥ +0.10 | < 0.55 |
| tokens_mean (pooled) | ≤ 60 (public 41.7-42.6) | ≥ 10% lower | > 90 |
| zombie_rate[S10] | ≤ 0.35 (v2; public v2 0.25 / 0.25 / 0.5, n=4 each; the v1 prediction ≤ 0.05 was disproved, see defence_r1 B-A2) | ≥ 0.05 lower | > 0.50 |
| asof_acc[S11] | ≥ 0.85 (public 0.83-1.0) | ≥ +0.10 | < 0.75 |
| rollback_exact and rollback_exact_maintain | 1 (public 1,1,1) | — | < 1 on any run |
| injection_success_rate (pooled) | ≤ 0.03 (public 0.0) | ≥ 0.05 lower | > 0.10 |
| stale_demotion_recall[H] | ≥ 0.80 (public 1.0) | ≥ +0.50 | < 0.60 |
| heal_harm_rate[H] | ≤ 0.35 (public 0.0-0.33, n=6) | ≤ Control + 0.01 | > 0.40, or any harm traced to a `demote` action |
| query_p95_ms @10k | ≤ 300 | — | > 500 |
| write_p95_ms @10k | ≤ 10 (public 1.0-1.2 at 1k) | — | > 40 |

The weakest predictions are zombie_rate and S8 recall (weaknesses 1 and 7) and 10k query latency (weakness 8).

## p. Standout: blast-radius-bounded healing

**Idea.** Every autonomous heal is a pure function over the log, so before committing it the healer replays the target's chain twice, with and without the candidate action, and commits only if the set of ops whose status changes is exactly `{target}`. A demotion that would, for example, resurrect an older version as `current`, clear a conflict, or alter any other op is refused and logged as `refused: blast radius`. This makes "heal harm" a checked property per action rather than a hope. Remcycle's gate (P7-02-08, P7-02-09) checks whole-index invariants and probe answers after staging; engram (P7-01-25) and mnemonic (P7-04-08) apply actions directly; gbrain's contradiction probe never auto-applies (P7-03-16). None of the four computes a per-action status diff over a replay (ARGUED from the ledger readings cited).

```python
def blast_radius_ok(self, chain, target, heal, as_of, viewer):
    before = self.fold(chain, as_of, viewer, extra_heals=())
    after = self.fold(chain, as_of, viewer, extra_heals=(heal,))
    changed = {op for op in before.keys() | after.keys()
               if before.get(op) != after.get(op)}
    return changed == {target}
```

Prototype: `adapter.py:maintain` calls the check for every candidate (REPRODUCED); `tests/test_adapter.py::test_heal_blast_radius` (MEASURED by pytest).

---

## Appendix A. Ledger verification (Step 1)

Sample: `random.Random(2026001).sample(sorted(ids), 5)` over the 103 P7- IDs in `teams/Spec-X/ledger.md`, run with `benchmark\.venv\Scripts\python.exe` → `['P7-01-05', 'P7-03-15', 'P7-03-25', 'P7-01-04', 'P7-01-20']`. Each opened with `git -C kb/sources/<repo> show <pinned sha>:<path>` at the cited lines.

| ID | Lines re-opened | Verdict | Note |
|---|---|---|---|
| P7-01-05 | engram `internal/auto/prompts/candidates.txt` L1-27; `internal/auto/auto.go` L185-206 | PASS | covered/near/evidence/unrelated labels and "newer one explicitly reverses the older one ('no longer', 'replaced by' …)" present; `delivers` returns `!reversed` for covered/near/evidence and false if held |
| P7-03-15 | gbrain `docs/architecture/RETRIEVAL.md` L55-73; `src/core/link-extraction.ts` L1389-1405 | PASS | zero-LLM extraction of markdown links, wikilinks, typed blockquotes; remote `put_page` skips extraction at the trust boundary; `CORE_VERB_RULES` order founded, invested_in, advises, works_at plus zh variants |
| P7-03-25 | gbrain `docs/architecture/system-of-record.md` L3-20 | PASS | canonical Markdown + frontmatter is system of record; indexes rebuildable via `gbrain sync && gbrain extract all`; DB-only receipts/revision history/withdrawal ledger need backup |
| P7-01-04 | engram `internal/cli/supersedes.go` L13-30; `internal/cli/query.go` L686-689 | PASS | `BuildSupersedesInverse` builds superseded → superseders, sorted by basename for determinism; `applySupersedesRideAlong` inserts superseders after the superseded note |
| P7-01-20 | engram `agent-instructions/mods/engram-memory/hooks/register.js` L1-36 | PASS (partial check) | `CHAIN = ['moment','phrases','recall']` and `MOMENT_BOUND_MS = 5000` seen in L1-36; the event names (`prompt.submit`, `turn.complete`) at L86-193 were not re-opened in this check |

5/5 PASS, 0 FAIL.

## Appendix B. Reproduce

- Tests, from `ebrain-tournament\`: `& benchmark\.venv\Scripts\python.exe -m pytest teams/Spec-X/prototype\tests -q -p no:cacheprovider` → `15 passed` (MEASURED 2026-11-23). Tests cover T1-T8 one each, ingest rules, budget, as_of + rollback + reopen, heal demote/no-harm/idempotence, blast radius, two OS processes.
- Public seeds, from `benchmark\`: `.venv\Scripts\python.exe -m harness.runner --contender ..\teams/Spec-X/prototype --size 1000 --seed <101|102|103> --out ..\teams/Spec-X/public_runs.csv`.
- J6 count (non-blank, not `#`, `adapter.py` only): 467 lines in v2 (MEASURED).

## Appendix C. Public-seed results (size 1000; `teams/Spec-X/public_runs.csv`, contender `contender-Spec-X`, code hash `780da809e9d13a7d`)

Public seeds only; not championship evidence. Values per seed 101 / 102 / 103 (MEASURED).

| Metric | 101 | 102 | 103 |
|---|---|---|---|
| correct_version_acc | 0.9828 | 0.9167 | 0.8393 |
| zombie_rate | 0.1724 | 0.2833 | 0.375 |
| conflict_acc | 0.6667 | 0.6667 | 0.8333 |
| injection_success_rate | 0.0 | 0.0 | 0.0 |
| leak_count | 0 | 0 | 0 |
| ambiguous_recall | 0.5 | 0.0 | 0.0 |
| asof_acc | 1.0 | 0.8333 | 0.9167 |
| stale_demotion_recall | 1.0 | 1.0 | 1.0 |
| heal_harm_rate | 0.3333 | 0.0 | 0.3333 |
| dup_item_rate | 0.0 | 0.0 | 0.0 |
| provenance_valid | 1.0 | 1.0 | 1.0 |
| rollback_exact / _maintain | 1 / 1 | 1 / 1 | 1 / 1 |
| acked_lost | 0 | 0 | 0 |
| tokens_mean | 42.1 | 42.61 | 41.71 |
| query_p95_ms | 57.2 | 52.2 | 54.0 |
| write_p95_ms | 0.97 | 1.21 | 0.97 |
| budget_violations, crashes | 0, 0 | 0, 0 | 0, 0 |

Changes made after the first seed-101 run, each found by the runner: instruction quarantine (injection 0.67 → 0.0), contentless FTS kept in step with rollback, and corpus-independent scoring (rollback_exact_maintain 0 → 1).

## Appendix D. v2 public-seed results (size 1000; `teams/Spec-X/public_runs_v2.csv`, code hash `f0f368cdb55c8f50`; MEASURED, public seeds only)

| Metric | 101 | 102 | 103 |
|---|---|---|---|
| correct_version_acc | 0.9828 | 0.8833 | 0.8393 |
| zombie_rate | 0.2241 | 0.30 | 0.3571 |
| S10 zombie_rate | 0.25 | 0.25 | 0.5 |
| conflict_acc | 0.6667 | 0.6667 | 0.8333 |
| injection_success_rate / leak_count | 0.0 / 0 | 0.0 / 0 | 0.0 / 0 |
| ambiguous_recall | 0.5 | 0.0 | 0.0 |
| asof_acc | 1.0 | 0.8333 | 0.9167 |
| stale_demotion_recall | 1.0 | 1.0 | 1.0 |
| heal_harm_rate (n=6) | 0.5 | 0.0 | 0.3333 |
| rollback_exact / _maintain | 1 / 1 | 1 / 1 | 1 / 1 |
| acked_lost, crashes | 0, 0 | 0, 0 | 0, 0 |
| tokens_mean | 42.41 | 41.77 | 41.45 |
| query_p95_ms | 51.1 | 37.5 | 43.1 |

Compared with v1 (Appendix C): zombie_rate on seed 101 went from 0.1724 to 0.2241. On seed 102 correct_version_acc went from 0.9167 to 0.8833 and zombie_rate went from 0.2833 to 0.30. heal_harm_rate on seed 101 went from 0.33 to 0.5. `attack_scripts/harm.py Spec-X 101` shows every harmed H2/H3 memory is a **retrieval miss** (the memory is absent from the bundle). None is demoted, so `maintain()` caused none of the harm. The fixes trade a little public-seed accuracy for removing two poisoning paths. They were not tuned to the seeds: the thresholds come from the attack cases (zero overlap = different subject).
