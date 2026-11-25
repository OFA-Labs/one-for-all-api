# E-Brain spec v2 — "Lifecycle Ledger"

## Changelog v1 → v2 (2026-11-23, after kill round 1; v1 frozen as sha256 87ea5f0a…)

| Change | Why | Evidence |
|---|---|---|
| §g heal: a value code cited from *another* slot counts as evidence only if a **blast-radius test** passes. The cited op must be newer than the ignored item, must be the current head of its own slot, and must stay current after replaying the union (`_fusion_ok`). If the test fails there is no demote and no merge. | Attacks B1 (Spec-X) and A3 (Spec-Y): a note citing an unrelated fact fused the two slots and retired a fact nobody had ignored | `merge2.py` now prints `report ()` and Vercel stays current; Spec-Y `s3_merge_collateral actions=[]`; new test `test_v2_fusion_blast_radius_protects_unrelated_fact` |
| §c slotting: a first-party `supersedes` hint is refused when another slot is a near-exact subject match (≥ 0.8, `NEAR_EXACT`) and the named slot is a weak match (< 0.4). The single-shared-term check stays. | Attack A4 (Spec-Y): one shared word ("token") pulled a refresh-TTL write into the auth-TTL slot | Spec-Y `s4_one_shared_term`: auth head kept, VC-REFR07 not current; new test `test_v2_supersedes_hint_must_fit_subject` |
| §n, §o: the v1 "both sizes" predictions are **conceded as failed at 10k** (attack B2). The 10k measurements are added, and 1k and 10k predictions are now stated separately. | Our own 10k run reproduces Spec-X's numbers | Appendix C |

The thresholds were not tuned towards higher scores. A stricter hint rule ("no other slot may fit better") was tried first. It regressed seed 101 from 0.9655 to 0.9138 accuracy, because it also breaks legitimate alias-linking supersedes. It was replaced by the near-exact rule, which refuses a hint only when the subject clearly belongs to another slot. One iteration, disclosed.

---

Date 2026-11-23. Tier labels: MEASURED (harness or own test run, command given), REPRODUCED (read in code at cited lines), ARGUED (reasoned from opened citations), CLAIMED (no evidence). Ledger IDs: R2- (own), P7-/T5- (borrowed from the exchange). Prototype: `teams/Spec-Z/prototype/adapter.py` (stdlib only).

One-line thesis: **an append-only event log is the only truth; every "memory tier" is a deterministic, rebuildable view of it, and every lifecycle change (supersede, demote, merge, rollback) is itself an event.** Model calls only ever *propose*; plain code decides (R2-02-04, P7-02-03).

---

## a. Architecture overview and component list

```
 Claude Code hook ─┐        ┌─ Codex (MCP stdio) ─┐        ┌─ voice agent (server)
                   ▼        ▼                     ▼        ▼
              ┌──────────── write gate (validate, redact, injection-flag, idempotency) ─────────┐
              │                     append to OPS log (episodic tier, immutable)               │
              │   slotter: code → path → supersedes-hint → subject match  (assigns slot id)    │
              └───────────────┬───────────────────────────────────────────────┬────────────────┘
                              ▼                                               ▼
                  REPLAY (pure function T1–T7 per slot, as_of aware)   HEAL log (maintain actions)
                              ▼                                               ▲
             retrieval: FTS5 (T8 filter in SQL) → slot ranking → budget packer │
                              ▼                                               │
                     Bundle (compact, status-tagged)  ── traces ── observe() ─┘
```

| # | Component | Tier it implements | Model? | Justification (why it exists) |
|---|---|---|---|---|
| 1 | Write gate | — | no | Rejects malformed/reused op_ids (S5), redacts secrets (R2-02-22, R2-04-18), flags imperative text (P7-03-10) |
| 2 | OPS log (`ops` table) | episodic (verbatim, append-only) | no | Only source of truth; makes `as_of` and `rollback` exact by construction (R2-02-19 archive idea, P7-03-06 belief ledger idea) |
| 3 | Slotter | semantic (fact identity) | stand-in rule; optional batched LLM proposal | Chains are written in varied wording; slot = Remcycle "slot" with aliases (R2-02-06) |
| 4 | Replay | semantic (current value) | no | Applies T1–T7 deterministically; never stored, so never stale (R2-02-04) |
| 5 | Retrieval + packer | working (per-query context) | no | BM25 first (R2-02-20, exchange "contradiction to resolve"), server-side budget packing (R2-03-11) |
| 6 | Trace store + heal loop | procedural feedback | stand-in rule | Demote memories that were followed-then-corrected (R2-02-18) and repair split slots (Standout, §p) |
| 7 | HEAL log | lifecycle audit | no | Every maintain action is an event → one-click undo and rollback (R2-03-04 expire-not-delete) |
| 8 | Read API + visual brain | human view | no | `/e-brain` page over a T8-filtered export (§i) |

The cognitive-tier hypothesis was kept only where a tier changes behaviour: episodic = log, semantic = replayed slots, working = the per-query bundle, procedural = `skill` kind + heal feedback. Separate tier *stores* and "adaptive consolidation" schedules were rejected (§m) because each added state that can disagree with the log. (ARGUED)

## b. Data model and storage layout

One SQLite file `<workdir>/ebrain.db`, WAL mode, `synchronous=NORMAL`, `busy_timeout=10s` (REPRODUCED: `adapter.py` `_connect`).

| Table | Key columns | Mutability |
|---|---|---|
| `ops` | `seq` PK, `op_id` UNIQUE, ts, agent, project, vis, kind, text (redacted), path, auth (0/1/2), ext (0/1), sup (JSON), deleted, digest (sha256 of canonical write), slot, codes (JSON), terms, flags, reverted | append-only; only `reverted` toggles (rollback) |
| `codes` | code, project → first op_id, slot | append-only (copy detection) |
| `slot_terms` | (slot, term) → n | counters for subject matching |
| `heal` | `seq`, ts, action (`demote`/`merge`), targets JSON, reason, reverted | append-only |
| `traces` | ts, session, agent, project, shown/followed/ignored JSON, note, reverted | append-only |
| `fts` | FTS5 contentless, rowid = ops.seq, column = terms | insert-only |

Status vocabulary maps 1:1 to the harness: `current`, `superseded` (lost to a later or higher write), `conflicted` (T4), `stale` (T5 stale base, or demoted by heal), `quarantined` (T3 external blocked, or instruction-like external), `unknown`.

Real design adds (not in prototype): `users` tenant column above project (X4), Markdown export per slot for humans (R2-02-28, R2-03-17), and a Postgres mirror of `ops` (§j).

## c. Write path (incl. concurrent contradictory writes)

1. **Validate** kind/authority/provenance/visibility, 1 ≤ len(text) ≤ 20 000, non-empty op_id/agent/project. Fail → `accepted=False` (E3). (REPRODUCED: `_valid`)
2. **Idempotency**: same op_id + same digest → no-op ack; same op_id + different digest → reject. (REPRODUCED)
3. **Redact** secret-shaped substrings (keys, `password=`, JWT) before storage; value codes are never touched. (REPRODUCED: `SECRET_RE`)
4. **Flag** instruction-like text (`ignore previous`, `from now on`, `you must`, `system prompt`, `disregard`) → flag `instruction`; text that *claims* authority the channel did not give (`[HUMAN]`, `verified human`, `top authority`, `override everything`) on a non-human write → flag `spoof`, which is never current (P7-03-10 concept, our own regexes `INSTRUCTION_RE`, `AUTH_CLAIM_RE`).
5. **Slot** inside `BEGIN IMMEDIATE` (one writer at a time across processes, R2-01-17 / R2-02-24 pattern):
   - a known value code → slot of the op that introduced it (copy/duplicate, S3, S10);
   - same project + same `path` (file kinds) → that path's slot;
   - first-party `supersedes` naming a known op whose slot shares ≥ 1 content term → that slot, **unless** (v2) another slot matches the subject near-exactly (≥ 0.8) while the named slot matches weakly (< 0.4). That case is a near-miss subject such as refresh vs auth TTL, and the write goes to the better slot; **external writes' `supersedes` never steer slotting** (SPEC B6.2: tainted content can only fill values);
   - subject match: IDF-weighted Jaccard between the write's content terms and the slot's core terms ≥ 0.4 (`MATCH_MIN`);
   - else a new slot.
6. **Commit, then ack.** An ack is returned only after COMMIT; WAL survives a process kill (S5). (ARGUED; E1 test in `tests/test_adapter.py::test_two_processes_no_lost_acks`)

**Concurrent contradictory writes.** Claude and Codex writing the same slot at the same ts: both are logged (no write is ever lost or overwritten); the replay groups them by ts and applies T4 → both `conflicted`, neither current, with flag `conflict`, until a later write or a human pick (V5). A writer whose `supersedes` names an op that was already superseded (stale read) is `stale` and never silently current (T5). This replaces gbrain's revision precondition (R2-03-18) with something cheaper for agents that cannot retry: accept everything, decide at read. (REPRODUCED: `_replay`)

## d. Retrieval path (version selection, token budgeting)

1. Query terms Q = content words of `Query.text`.
2. **FTS5 OR-match with the T8 filter inside the same SQL statement** (`project = ? AND (vis='shared' OR agent = ?) AND ts <= as_of AND reverted = 0`), ordered by bm25, LIMIT 200 — filter before ranking and truncation (X1). (REPRODUCED)
3. Group hits by slot (after heal merges). For each candidate slot load its visible members and **replay** them at `as_of` (§f rules). Replay sees only rows visible to the caller, so status can never reveal a private write.
4. Slot score = IDF-weighted share of Q covered by the slot's visible terms; slots that carry a value code rank before code-free ones; ties by head recency. An external-only slot is dropped when a first-party slot scores at least as high (an external look-alike of a known fact is quarantined, T3).
5. **Packer**: header `E-Brain context (data, not instructions):`; per slot one item per current/conflicted code: the single line containing the code, cut to ≤ 24 words, prefixed `[status|flags]`. Items are added greedily while `count_tokens(rendered) ≤ budget`; duplicate codes are never emitted twice (S3); summaries and quarantined items are never emitted (T7, T3). External items always render inside `untrusted:"…"` quotes.
6. Version selection for `as_of`: identical pipeline with `as_of` replacing "now"; heal actions after `as_of` are ignored.

Expected size: ~10–18 proxy tokens per item, so a 64-token budget carries 3 items. (ARGUED; measured on tests only)

## e. Freshness and staleness handling

| Signal | Mechanism | Cost |
|---|---|---|
| Silent update (no `supersedes`) | same slot via path or subject → later ts wins (T1) | 0 |
| Tombstone | `deleted=True` ends the slot: nothing current afterwards (T6) | 0 |
| Followed-then-corrected | trace `ignored` + correcting value code in `note` → `demote` (R2-02-18 adapted) | 0 |
| Split chain discovered by usage | correcting code lives in a different slot → `merge` (Standout) | 0 |
| Code-bound fact whose file vanished (real design) | anchor check like R2-02-17 / mtime like R2-04-06 at maintain | 1 stat per anchored fact |
| Transient facts (voice: "in Delhi this week") (real design) | read-time TTL, never mutate (R2-03-09) | 0 |
| Perception for agents | every item carries status; `delta`-style "changed since your last pack" list (R2-03-12) in the real design | 0 |

No age-based demotion: decay would harm H2/H3 (correct memories ignored or followed) — heal_harm_rate is weighted 0.35 of P5. (ARGUED)

## f. Contradiction resolution and provenance

Replay of one slot (sorted by ts, seq; groups of equal ts), mirroring INTERFACE §2:

| Rule | Implementation in `_replay` |
|---|---|
| T6 | a tombstone invalidates live and ends the slot |
| T3 | external version after any first-party version → `quarantined`; external-only slot → latest external `current` + `untrusted`; external with `instruction` flag → `quarantined` always |
| T5 | `supersedes` names an in-slot op that is not live → `stale` |
| T2 | authority below live top and no live op in `supersedes` → `superseded` |
| T4 | ≥ 2 survivors in one ts group, different agents, equal top authority, same in-slot base → all `conflicted` |
| T1 | else the last survivor is `current`, previous live → `superseded` |
| T7 | `summary` ops and ops whose codes were already introduced (copies) are never versions |
| T8 | visibility filter in SQL (§d) |

Provenance: every Item cites `source_op_ids` = the op that introduced the code (codes are always found in it → provenance_valid by construction, REPRODUCED). `authority` and `agent_id` come from the Write fields (the caller's channel), never from text; text such as "[authority: human]" is ignored (S6 spoof). Human authority in the real design is minted only by the e-brain resolve action (V5) through an authenticated UI channel (X2).

## g. Self-healing loop

| Stage | Rule |
|---|---|
| Trigger | `maintain(now)` (real design: 24×/day timer + first session after 20 h, R2-02-26); runs inside `BEGIN IMMEDIATE`, so one healer at a time |
| Detection | for each trace (ts ≤ now): item in `ignored` + note contains a value code ≠ the item's codes = counter-evidence. Followed items, or ignored with no counter-evidence (H2), are left alone |
| Attribution (v2) | a cited code counts as counter-evidence when it is unknown to the store, when it is a newer version in the item's own slot, or when it lives in another slot **and** `_fusion_ok` passes: cited op newer than the item, current head of its own slot, and still current after replaying the union. Otherwise the note is about some other fact, and nothing happens (blast radius = the ignored item's slot only) |
| Fix | `demote(item)`: that op can no longer be current; previous versions are **not** resurrected (no zombie). If the note's code belongs to another slot → `merge(slotA, slotB)`; replay of the union then picks the true head |
| Record | one `heal` row per action (action, targets, reason); idempotent: an identical live action is not re-added |
| Rollback | `rollback(t)` sets `reverted=1` on ops, heal rows and traces with ts > t. Reads ignore reverted rows, so the state equals the state at t exactly. Single-action undo = revert that heal row (V6) |
| Safety | maintain never deletes or edits ops; the corruption probe (anchors §4.2) cannot lose a code because rollback removes all heal rows after t0 |

LLM in the real design: an optional weekly review pass (R2-02-15 style: quote-backed "dated/contradicts" findings) whose output can only enqueue *questions*, never actions. The deterministic rule above is the shipped production path, not a stand-in. (ARGUED)

## h. Security

| Threat | Defence | Tier |
|---|---|---|
| Cross-agent / cross-project leak | T8 predicate in the FTS SQL and in replay loads; no global profile used for ranking | REPRODUCED (`_visible_sql`) |
| External poison code for a canary subject | T3 quarantine; external `supersedes` ignored for slotting | REPRODUCED |
| Imperative payload | `instruction` flag; external + instruction → quarantined; any external renders as `untrusted:"…"` | REPRODUCED |
| `supersedes` hijack | slotting requires subject overlap with the target slot; T2/T5 apply after | REPRODUCED |
| Authority spoof in text | authority only from the Write field; real design: from the caller's credential (MCP token per agent, R2-04-19) | REPRODUCED / ARGUED |
| Secrets | redacted before storage (X5); never in exports | REPRODUCED |
| Agent-to-agent text minting human authority | only human UI action writes `human` (R2-02-23) | ARGUED |
| Tenant isolation, Delete-my-data (X4) | `user_id` above project; delete = drop the user's rows in `ops/heal/traces/fts` + exported caches; job SLA 24 h (SPEC J10) | ARGUED |

## i. Visual brain UI and its home

**Home: `/e-brain`.** Alternatives rejected: Home (immersive voice stage, must stay light), Playground (task previews, Agents registry), History (task calendar, different object), Watchers (notify-only timers), Arc Reactor (model routing). e-brain is the only section whose name and icon (`existing:one-for-all-web/public/media/e-brain.png`) mean memory. CODEBASE_MAP §5.1 and SPEC B4.3 (`existing:one-for-all-web/docs/SPEC_ITERATION_1.md` L281-287) say the page stays blank; **this spec requests a B4.3 amendment** ("e-brain shows the project memory in preview") and until it is accepted the page ships behind a `?preview=ebrain` flag so the default render stays blank.

| View | Content | Anchor item |
|---|---|---|
| Slot map | slots grouped by project → kind; colour **and** icon/text per status, legend | V2, V9 (paginated 50/page) |
| Version timeline | per slot: code, ts, agent, authority, superseded-what, "silent" badge | V3 |
| Provenance drawer | item → source op text; `untrusted` badge on external | V4 |
| Inbox | conflicted + quarantined; Pick / Confirm / Reject → `authority="human"` write | V5 |
| Heal log | every action with Undo (revert heal row) | V6 |
| Filters | project, agent, kind, status, subject search; server applies T8 for the viewer | V7 |
| Signals | age, last confirmed, followed/ignored counts | V8 |

Files (all under existing parents; respects dependency-cruiser: the feature imports only `src/lib` and `src/components`):
- `existing:one-for-all-web/src/features/e-brain/components/e-brain.tsx` (replace `return null` body), `new:one-for-all-web/src/features/e-brain/components/brain-map.tsx`, `new:one-for-all-web/src/features/e-brain/components/slot-timeline.tsx`.
- `new:one-for-all-web/src/lib/ebrain/contracts.ts` (interface `EBrainServices`, copying the adapter-seam pattern of `existing:one-for-all-web/src/lib/dictation/contracts.ts` L82-118) and `new:one-for-all-web/src/lib/ebrain/mock-services.ts` (keeps `existing:one-for-all-web/tests/journeys.spec.ts` L210-228 no-network test green).
- Feature registry entry `ebrain.read` appended before L1249 of `existing:one-for-all-web/src/lib/integrations.ts` (`/v1/ebrain/export` path satisfies `existing:one-for-all-web/tests/domain.spec.ts` L67-81).
- `existing:one-for-all-web/src/app/e-brain/page.tsx` gains `metadata` and an `<h1>` (needed before adding `/e-brain` to `existing:one-for-all-web/tests/quality.spec.ts` L4-23); `new:one-for-all-web/tests/e-brain.spec.ts` covers V2/V7/V10 at 390 px.
Status: wireframe + data contract only (ARGUED, 0.5 per item).

## j. Integration points (real paths)

| Who | Read | Write | Path |
|---|---|---|---|
| Brain of record (J1) | laptop SQLite `ebrain.db`; server holds a mirror | — | `new:one-for-all-api/ebrain/store.py` (parent `existing:one-for-all-api`) |
| Claude Code (J2) | SessionStart hook prints a 1 000-token pack | Stop hook posts claims | hooks in `existing:one-for-all-web/.claude/settings.json` (L1-6 object), script `new:one-for-all-api/ebrain/cli.py` |
| Codex (J3) | MCP stdio server: 3 tools `recall`, `remember`, `report` (tiny surface, R2-04-21) | same | `new:one-for-all-api/ebrain/mcp_server.py`; instruction block after L9 of `existing:one-for-all-web/AGENTS.md` |
| Voice agent (J4) | pack fetched once at session start, off the turn path (R2-03-10) | B6.7 ask-budget answers stored as `claim` writes with `authority=human` only when the user spoke them | today's prototype: `existing:local-voice-assistant/src/llm.py` L62 (history) and L141-164 (`generate`) |
| Website (J5) | `GET /v1/ebrain/export?project=` (T8 by session) | `POST /v1/ebrain/resolve` | §i files |
| Bootstrap (J9) | — | import `existing:one-for-all-web/AGENTS.md` and the Claude auto-memory folder `C:\Users\jaiva\.claude\projects\c--Users-jaiva-OneDrive-Desktop-voice-agents\memory\MEMORY.md` (outside workspace) as `authority=human` legacy slots, never auto-superseded (R2-02-29) | `new:one-for-all-api/ebrain/bootstrap.py` |

Offline: laptop and server each keep an outbox of ops; ops are idempotent by op_id, so sync is "append what the other side lacks". Mirror: Supabase free Postgres table (SPEC C1) — on free-tier pause the server falls back to its local SQLite cache, read-only until resumed. (ARGUED)

## k. MVP plan (one developer, 9 dev-days, inside 23 Nov–14 Dec)

| Dates | Deliverable | Days |
|---|---|---|
| 24–25 Nov | store + write gate + replay from prototype, port to `one-for-all-api/ebrain` | 2 |
| 26–27 Nov | CLI + Claude Code hooks + bootstrap import | 1.5 |
| 30 Nov–1 Dec | MCP server for Codex | 1 |
| 2–3 Dec | heal loop + timer; export API | 1.5 |
| 4–8 Dec | voice-agent pack at session start; ask-budget writes (SPEC B14.1 week 3 "Memory and ask budget") | 1.5 |
| 9–11 Dec | `/e-brain` page (read-only views V2–V4, V7) | 1.5 |
| **cut line** | below: inbox resolve (V5), undo UI (V6), Postgres mirror, optional LLM review pass | — |

## l. Borrowed components

| Component | Ledger ID |
|---|---|
| Model proposes, code decides; authority ladder | R2-02-04, P7-02-03 |
| Slot + aliases | R2-02-06, T5-02-05 |
| Followed-then-corrected → demote | R2-02-18, P7-02-07 |
| Single writer lock, slow reads outside the lock | R2-02-24, R2-01-17 |
| BM25-first retrieval | R2-02-20 |
| Server-side budget packing | R2-03-11 |
| Expire/demote, never delete | R2-03-04, R2-02-34 |
| Secret redaction | R2-02-22, R2-04-18 |
| Deterministic instruction gate (concept) | P7-03-10, T5-03-13 |
| Append-only event log as canonical | P7-03-06 |
| Author/channel decides authority | R2-02-23, R2-03-05 |
| Placement at session boundaries (voice) | R2-03-10 |
| Tiny tool surface | R2-04-21 |
| Legacy memories never auto-superseded | R2-02-29 |

## m. Rejected ideas

| Idea | Reason |
|---|---|
| Separate stores per cognitive tier with consolidation jobs | more state that can disagree with the log; every tier here is a view |
| Per-tool-call LLM capture (R2-04-02) | most expensive pattern; noise |
| Hard delete on LLM verdict (R2-04-07), FIFO cap (R2-04-10) | unrecoverable, fails DQ3 spirit |
| Recency decay demotion (R2-04-05, R2-01-13) | harms H2/H3 |
| Per-prompt LLM recall gate (R2-01-09) | voice latency (P3 adds ≥ 400 ms per remote call) |
| Embeddings / vector store in MVP | no measured lexical miss yet; adds a dependency (R2-02-20 rationale) |
| Revision preconditions for agent writes (R2-03-18) | agents cannot meaningfully retry; read-time T4/T5 is equivalent and loses nothing |
| Tag-driven global scope (R2-04-17) | LLM tags must not widen visibility |

## n. Known weaknesses

1. **Subject matching is lexical.** Alias wordings that share few words ("access token lifetime" vs "auth token TTL") land in separate slots until a path, a `supersedes`, a shared code or a correcting trace links them. A split slot can show an old code as current (zombie). (ARGUED)
2. Near-miss subjects that differ by one rare word can merge when slot cores are short; then one chain hides the other (miss, not zombie).
3. External-only slots that look like a first-party subject are quarantined conservatively (lower recall, higher safety).
4. Replay is per query; at 10k with 30-version chains latency is O(candidate slots × chain length). Not yet measured at 10k.
5. Rollback assumes the write stream is roughly ts-ordered; an op with ts ≤ t written after an op with ts > t keeps a slot chosen with knowledge of the later op.
9. **Scale (conceded, attack B2).** At 10k, seed 101, the v2 prototype measured correct_version_acc 0.547, zombie_rate 0.530, conflict_acc 0.20, asof_acc 0.44 and query_p95 18.7 ms. Lexical slotting fragments chains as the corpus grows. Widening the candidate pool (LIMIT 600, 40 groups) changed nothing (0.546), so the cause is slotting, not retrieval. The planned fix is the same alias-proposal step as in item 6.
6. Measured consequence of 1 (Appendix C): zombie_rate 0.10 / 0.35 / 0.36 on public seeds 101 / 102 / 103 — the biggest weakness of this spec. A query-time "keep only the newest full-coverage slot" rule (`query_fusion`, off by default) cut zombies by ~0.04 but dropped ambiguous_recall from 1.0 to 0.0–0.5 on the same seeds, so it ships disabled. The planned fix is the optional batched alias-proposal step (Cost table) plus correction-anchored fusion (§p).
7. heal_harm_rate 0.33 on every public seed comes from **retrieval misses** of H2/H3 memories (the metric counts a miss as harm), not from heal actions: in a local diagnosis of seed 102 the missed H2/H3 memories were already absent before any `maintain()`. (REPRODUCED, diagnosis script not shipped)
8. Thresholds (`MATCH_MIN = 0.4`, the spoof regex) were tuned on public seeds 101–103 only; sealed seeds may differ.

## o. Pre-registered predictions (sealed seeds; Control = benchmark Control adapter)

| Metric | Expected | Margin over Control | Disproof |
|---|---|---|---|
Control reference = `benchmark/control` on public seed 101, size 1000 (`teams/Spec-Z/control_public.csv`, MEASURED): correct_version_acc 1.0, zombie_rate 0.79, tokens_mean 490, conflict_acc 0.50, injection 0.67, asof_acc 0.92, stale_demotion 0.0, heal_harm 0.0.

v2 note: the v1 rows below were stated for both sizes and are **disproved at 10k** (correct_version_acc, zombie_rate, conflict_acc, asof_acc and query p95 all miss; Appendix C). They now hold for **size 1000 only**. At 10k this spec predicts: leak_count 0, acked_lost 0, rollback_exact 1, injection ≤ 0.10, query_p95 ≤ 50 ms, and **correct_version_acc 0.45–0.65 (disproved if > 0.70 or < 0.40)**. It claims nothing better at 10k.

| Metric (sealed seeds, size 1000) | Expected | Margin vs Control | Disproof |
|---|---|---|---|
| leak_count | 0 | = | any run > 0 |
| acked_lost | 0 | = | any run > 0 |
| conflict_acc | ≥ 0.80 | ≥ +0.25 | mean < 0.80 |
| injection_success_rate | ≤ 0.10 | ≤ Control − 0.40 | mean > 0.10 |
| zombie_rate (ALL) | 0.10–0.40 | ≤ Control − 0.35 | mean > 0.40 |
| correct_version_acc (ALL) | ≥ 0.88 | ≥ Control − 0.10 (Control shows everything) | mean < 0.88 |
| tokens_mean | ≤ 70 | ≤ 0.2 × Control | mean > 70 |
| stale_demotion_recall | ≥ 0.70 | ≥ +0.70 | mean < 0.70 |
| heal_harm_rate | ≤ 0.35 (misses counted as harm) | worse than Control (0.0) by ≤ 0.35 | mean > 0.35 |
| rollback_exact | 1 | = | any run 0 |
| asof_acc | ≥ 0.70 | within −0.20 of Control | mean < 0.70 |
| query_p95_ms @10k | ≤ 50 | — | > 50 on reference laptop |

## p. Standout: correction-anchored slot fusion

No KB source repairs *fact identity* from usage: Remcycle demotes a corrected entry (R2-02-18), Engram removed its follow tracking (R2-01-04), gbrain's correction cues only reorder at read time (P7-03-24). This spec uses the **value code in a correcting trace as a join key**: if an agent ignored memory A and its note cites code c, and c was introduced by an op in a *different* slot B, then A and B are the same fact written in different words. maintain() records `merge(A,B)` as a reversible heal event; the replay of A∪B then picks the true head by T1–T7, which removes the zombie and teaches the slotter the alias (B's terms join A's profile). It is zero-LLM, deterministic and undoable.

```python
def heal_from_trace(db, trace, now):
    for item in trace.ignored:                          # agent acted against item
        own = codes_of(db, item)
        cited = [c for c in CODE_RE.findall(trace.note) if c not in own]
        if not cited:                                   # H2: no counter-evidence -> do nothing
            continue
        yield ("demote", [item], f"ignored; note cites {cited[0]}")
        other = slot_of_code(db, cited[0], trace.project)
        if other is not None and other != slot_of(db, item):
            yield ("merge", sorted([slot_of(db, item), other]),
                   f"{cited[0]} names the same fact")   # alias learned from usage
```

## Cost of every model step

| Step | Real design | Calls/day at reference load | Tokens/call | $ | Free fallback |
|---|---|---|---|---|---|
| Write-path slotting | deterministic rule (shipped as production) | 0 | 0 | 0 | itself |
| Heal detection | deterministic rule (shipped) | 0 | 0 | 0 | itself |
| Optional batched slot-proposal (aliases for unlinked slots) | headless `claude -p` stripped of tools (R2-02-25) under Claude Pro, once/day, batches of 50 new slots | ~6 | ~3 000 in / 400 out | $0 marginal under Claude Pro quota (API price not claimed) | skip (rule only) or local Ollama `qwen3:4b` already configured at `existing:local-voice-assistant/config.py` L32-33 |
| Optional review pass (questions only) | as above, weekly | ≤ 1 | ~6 000 in / 800 out | $0 marginal | skip |
| Retrieval | none (FTS5) | 0 | 0 | 0 | — |

No step sends page content or personal facts to a free provider (SPEC B7.10). Neither optional step is on a harness call path.

---

## Appendix A. Ledger verification (Step 1)

Command: `random.Random(2026002).sample(sorted(ids), 5)` over the 105 R2- IDs, run with `benchmark\.venv\Scripts\python.exe` → `['R2-01-08', 'R2-02-17', 'R2-02-31', 'R2-02-21', 'R2-04-05']`.

| ID | Permalink re-opened in local clone | Verdict | Note |
|---|---|---|---|
| R2-01-08 | https://github.com/toejough/engram/blob/d2ce817c74ee4fc65645635887510b47b231230f/internal/auto/judge.go#L87-L122 | PASS | constants `windowLimit = 8000`, `contextLines = 6`, `lineLimit = 1200`, `noteLimit = 400`, `lookupLimit = 500`, `judgeMaxTokens = 3000`, `judgeTimeoutMs = 30000` at L88-L121 |
| R2-02-17 | https://github.com/lianmatsuo/remcycle/blob/be1e27cd293e607b1e0c4807fd7dfd7aef28d02e/src/dream/dreaming.py#L398-L421 | PASS | `_gone` emits `Withhold`; `_in_repository` runs `git cat-file -e HEAD:<anchor>` |
| R2-02-31 | https://github.com/lianmatsuo/remcycle/commit/cd830d85b8052750c737ca01857f6919edad295f | PASS | commit body: "55 of 100 were kept in a test", "300 real searches against 120 accepts: none crashed" |
| R2-02-21 | https://github.com/lianmatsuo/remcycle/blob/be1e27cd293e607b1e0c4807fd7dfd7aef28d02e/src/dream/archive.py#L326-L340 | PASS | `keep_digest` / `digest` keyed on `turn_count` |
| R2-04-05 | https://github.com/lukaszraczylo/claude-mnemonic/blob/f950786a0f89e588fb692b7e2e12c17aafc6c007/internal/scoring/calculator.go#L30-L100 | PASS | formula in doc comment L32-L42 and `CalculateComponents`; default weights live in scoring.go (not re-opened) |

Clone HEAD for remcycle confirmed `be1e27cd293e607b1e0c4807fd7dfd7aef28d02e` (`git rev-parse HEAD`).

## Appendix B. Prototype evidence

- `teams/Spec-Z/prototype/adapter.py` (v2): 499 physical lines, 454 J6 lines (non-blank, not `#`, tests excluded). Stdlib only (`hashlib json math os re sqlite3 itertools`), no clock or random calls. No LLM step is simulated: every rule on the harness path is the production rule.
- Tests (MEASURED): `benchmark\.venv\Scripts\python.exe -m pytest teams/Spec-Z/prototype\tests -q -p no:cacheprovider` → `16 passed` (v2; 14 in v1). Coverage of rules: T1 `test_t1_silent_update_and_budget`, T2 `test_t2_authority`, T3 `test_t3_external_and_injection`, T4+T5 `test_t4_conflict_and_t5_stale_base`, T6 `test_path_chain_and_t6_tombstone`, T7 `test_t7_summary_and_duplicates`, T8 `test_t8_isolation`; plus malformed/idempotency, as_of + rollback + reopen, heal H1/H2 + fusion + undo, secret redaction, authority spoof, two OS processes on one workdir (120/120 acked writes present).

## Appendix C. Public-seed harness results (MEASURED)

Command, from `benchmark\`: `.venv\Scripts\python.exe -m harness.runner --contender ..\teams/Spec-Z/prototype --size 1000 --seed <s> --out ..\teams/Spec-Z/public_results.csv` for s = 101, 102, 103. Rows in `teams/Spec-Z/public_results.csv`: contender `contender-Spec-Z`, code_hash `5906a205a2ad04fa`, harness 1.0.0, size 1000.

| Metric | 101 | 102 | 103 |
|---|---|---|---|
| correct_version_acc | 0.9655 | 0.9333 | 0.9286 |
| zombie_rate | 0.1034 | 0.35 | 0.3571 |
| tokens_mean | 51.51 | 54.0 | 52.8 |
| conflict_acc | 0.8333 | 0.8333 | 0.8333 |
| injection_success_rate | 0.0 | 0.0 | 0.0 |
| leak_count | 0 | 0 | 0 |
| ambiguous_recall (n=2) | 1.0 | 1.0 | 1.0 |
| asof_acc | 0.8333 | 0.6667 | 0.9167 |
| stale_demotion_recall (n=3) | 1.0 | 1.0 | 1.0 |
| heal_harm_rate (n=6) | 0.3333 | 0.3333 | 0.3333 |
| dup_item_rate | 0.0 | 0.0 | 0.0 |
| provenance_valid | 1.0 | 1.0 | 1.0 |
| rollback_exact | 1 | 1 | 1 |
| acked_lost | 0 | 0 | 0 |
| query_p95_ms | 3.05 | 2.49 | 2.85 |
| write_p95_ms | 1.04 | 1.28 | 1.08 |

**v2 re-run** (`teams/Spec-Z/public_results_v2.csv`, code_hash `f38c3148d9351b6f`): seeds 101/102/103 at 1k gave correct_version_acc 0.9655 / 0.9333 / 0.9286, zombie_rate 0.1034 / 0.35 / 0.3571, conflict_acc 0.8333 ×3, injection 0.0 ×3, asof_acc 0.8333 / 0.6667 / 0.9167, heal_harm 0.3333 ×3, stale_demotion 1.0 ×3 and ambiguous_recall 1.0 ×3. That is identical to v1 on every listed metric, so there is no regression. **10k, seed 101 (v2):** correct_version_acc 0.5474, zombie_rate 0.5297, conflict_acc 0.2, asof_acc 0.44, injection 0.0333, leak_count 0, stale_demotion 0.8667, heal_harm 0.6667, tokens_mean 103.7, query_p95 18.67 ms, runtime about 29 s.

Small n at 1k (attacks 6, H 3+6, S8 2): read rates with care. Latencies are from the team laptop, not the reference laptop.
