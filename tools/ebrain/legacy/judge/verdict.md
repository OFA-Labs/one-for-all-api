# RE-SCORE v2 decision: all three sealed seeds (supersedes the leaderboard below)

## INCONCLUSIVE. Leader: Spec-Y. No contender KILLED. Control DISQUALIFIED (DQ2).

| Rank | Contender | Final | MC | Final without ARGUED credit |
|---|---|---|---|---|
| 1 | **Spec-Y** | **59.64** | **59.14** | 51.14 |
| 2 | Spec-Z | 56.23 | 54.90 | 48.09 |
| 3 | Spec-X | 18.53 | 1.88 | 10.03 |
| — | Control | 38.21 (DQ2, injection 0.594) | 41.83 | — |

- **Gap between Spec-Y and Spec-Z:** 3.41, which is ≤ 5.00, so the result is INCONCLUSIVE (§7.3).
- **Lead with ARGUED credit removed:** 3.05, which is not more than 5.00 (§7.4b).
- **Control rule:** not triggered. Control is disqualified, and its MC of 41.83 is below Spec-Y's and Spec-Z's.
- **Disqualifier changes:** none.
  - Spec-Z's single `rollback_exact_maintain` = 0 was checked with the §4.2-intent diagnostic: no ground-truth-current code was lost, so it is not DQ3.
  - Spec-X timed out at 10k on 2 of the 3 sealed seeds. That is scored as 0 under §0.3, not a disqualification.
- **Decisive experiment** (§7.5, unchanged): measure P4.V by rendering the Spec-Y and Spec-Z visual-brain pages and verifying V1–V10. This component is worth 0.72 Final points per point, with a maximum swing of 7.56, which is at least the 3.41 gap.
  - Spec-Z overtakes only if its measured V exceeds Spec-Y's by more than 4.24 points (gap 3.41 + 0.72 × (V_Y − V_Z − 0.5) < 0).
  - Spec-Y becomes WINNER if its lead with ARGUED credit removed then exceeds 5.00.
- **Sections C–G below still stand.** The leader is unchanged, and the new data reinforce ADR-5 on Control's recall: Control's correct_version_acc is 0.962 at 1k and 0.866 at 10k, against Spec-Y's 0.903 and 0.567.

---

# E-Brain Tournament: Verdict (Phase 8)

Chief Judge, 2026-11-23. Scored with `judge/anchors.md` v1.0 (sha256 `CC7FDCB1…8AFF`); the evidence is in `judge/scorecard.md`. Labels stay blinded.

## Decision: INCONCLUSIVE. Leader: Spec-Y. No contender KILLED. Control DISQUALIFIED (DQ2).

There are two independent reasons:
1. **The top two are within 5 points.** Spec-Y leads Spec-Z by 4.02, which is ≤ 5.00 (§7.3).
2. **The evidence is insufficient (§7.4).**
   - (a) There is 1 sealed seed, not 3.
   - (b) With ARGUED credit removed, the lead is 48.89 − 45.23 = 3.66, which is not more than 5.

Either reason alone gives INCONCLUSIVE.

The Control rule (§7.2) is **not triggered**. Control is disqualified for poisoning (injection 0.556 mean, poison and spoof classes at 1.0), and even without that its MC of 40.05 is below every spec's.

## A. Leaderboard

| Rank | Contender | Final / 100 | MC | Final without ARGUED credit | Status |
|---|---|---|---|---|---|
| 1 | **Spec-Y** (versioned fact-chain graph) | **57.39** | **56.00** | 48.89 | qualified, leader |
| 2 | Spec-Z (lifecycle ledger) | 53.37 | 50.90 | 45.23 | qualified |
| 3 | Spec-X (event-sourced fold) | 51.97 | 48.45 | 43.47 | qualified |
| — | Control | 36.93 | 40.05 | 36.93 | **DISQUALIFIED: DQ2 unmitigated poisoning** |

Parameter scores (0–10):

| Contender | P1 Retr (15) | P2 Tok (10) | P3 Lat (8) | P4 Fresh+Vis (12) | P5 Heal (15) | P6 Truth (10) | P7 Sec (10) | P8 Scale (2) | P9 Cost (5) | P10 Integ (8) | P11 Evid (5) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Spec-Y | 3.54 | 7.57 | 9.80 | 3.00 | 5.00 | 4.38 | 9.04 | 3 | 5.0 | 6.3 | 8.0 |
| Spec-Z | 3.06 | 6.85 | 9.95 | 2.70 | 5.05 | 3.63 | 7.38 | 3 | 5.0 | 6.3 | 8.0 |
| Spec-X | 2.87 | 7.73 | 4.23 | 3.00 | 5.00 | 4.27 | 9.04 | 3 | 5.0 | 6.3 | 8.0 |
| Control | 5.74 | 5.52 | 8.95 | 0.00 | 1.16 | 4.63 | 0.50 | 3 | 5.2 | 2.8 | 6.67 |

## B. Battle report (one kill round, attacks run against v1 code)

| Target | Attacks | Outcome in v2 | Measured proof | Kill? |
|---|---|---|---|---|
| Spec-Y | External hijack with a new path (DQ2 class 0.5 on seed 102); T5 stale base; predictions disproved | Hijack fixed (rule order). T5 partly fixed. Predictions conceded. | Hijack class 0 in all 3 scored runs and in the judge re-run | No |
| Spec-X | Cue word demotes a correct fact; cross-chain `supersedes` erases a human fact; S10 zombies | Both fixed (same-subject evidence, slot-overlap rule). S10 conceded. | Defender re-ran at MEASURED tier; judge's 1k re-run matches the spec's table | No |
| Spec-Z | Merge heal erases an unrelated fact; one shared term crosses subjects; five 10k predictions fail | `_fusion_ok` blast radius and the near-exact slot rule fixed the first two. The 10k collapse was conceded. | Defender MEASURED; the sealed 10k values are what was scored | No |

- Every attack aimed at a disqualifier was refuted by measured v2 behaviour.
- Every attack about 10k accuracy is already reflected in the sealed MEASURED scores, so its deduction is 0 (§4.4). No 10+ point issue stands.
- **Permalink audit:** 24 of 24 OK, with no fabrication.
- **Judge re-runs:** every deterministic metric matches the reported value.

## C. Leading architecture (provisional): Spec-Y, the versioned fact-chain graph

| Layer | Mechanism |
|---|---|
| Store | One SQLite file in WAL mode. Append-only `ops`; a `codes` value registry; a `terms` inverted index that carries vis and agent; `traces`; a `heal` overlay that never mutates `ops`. |
| Write | Ingest gate: validate, make idempotent by digest, redact secrets, flag injection or spoof, fix provenance. The slot resolver assigns a chain by path, then a known `supersedes`, then term overlap with a discriminator guard. The role (version, copy, derived, tomb, note) comes from the value registry. |
| Read | T8 applied in SQL, then idf chain ranking, then replay of T1–T7 per chain up to a horizon (as_of), then lineage status (a restatement takes its origin's status), then greedy budget packing. No model call. |
| Heal | Demotion happens only on counter-evidence in a trace (a fingerprint or path). Each action is an overlay row, so `rollback` deletes ops, heals and traces after t. |
| Integration (ARGUED) | Laptop brain of record with a Supabase free-tier replica for the EU voice backend. Claude Code SessionStart and Stop hooks plus an MCP server; a Codex AGENTS.md block; a voice pack fetched at session start; the `/e-brain` page through `/v1/ebrain/*`. |

## D. Why it leads, measured (Δ against the runner-up and against Control)

| Evidence (MEASURED, mean of 3 runs) | Spec-Y | Spec-Z | Spec-X | Control |
|---|---|---|---|---|
| Composite of harness metrics (MC) | **56.00** | 50.90 | 48.45 | 40.05 |
| correct_version_acc, pooled at 10k | **0.646** | 0.553 | 0.641 | 0.844 |
| conflict_acc | **0.55** | 0.38 | 0.53 | 0.67 |
| asof_acc | **0.70** | 0.59 | 0.67 | 0.72 |
| injection_success_rate | **0** | 0.011 | **0** | 0.556 |
| query p95 at 10k | 21 ms | **19 ms** | 1029 ms | 41 ms |
| tokens_mean | 91 | 88 | **58** | 488 |
| stale_demotion_recall | **1.0** | 0.96 | **1.0** | 0.09 |

**Why Spec-Y leads.** It is the best spec on accuracy (P1), conflicts and time travel (P6), and security (P7 tied with Spec-X), and it is within 0.15 of the best on latency. Spec-Z loses on 10k chain fragmentation (conflict_acc 0.20–0.28 at 10k) and a poison-class slip. Spec-X scores only 4.23 on P3 because its p95 query at 10k is 1.0 s.

**Why the lead is not decisive.** Spec-Y's lead over Spec-Z is 4.02, and 3.66 of those points remain once ARGUED credit is removed.

## E. What the leader cannot solve (measured or self-disclosed)

| Gap | Evidence | Consequence |
|---|---|---|
| Split chains on silent, reworded writes | S1 zombie_rate 0.52 (scale 0 from 0.35 up); 10k pooled zombie 0.60–0.65 | Old values stay `current` beside new ones; P4.F = 0 |
| Self-heal harm at 10k | heal_harm_rate 0.83 and 0.80 at 10k (Control 0.13); the team argues these are retrieval misses (ARGUED) | P5.B = 0. Autonomous healing is not yet safe at scale |
| Retrieval recall at 10k | correct_version_acc 0.618–0.673, against Control's 0.84 | Control's ranker finds the current code more often |
| Ambiguous queries | ambiguous_recall 0.13–0.5 | P1.B = 1.0 |
| Private-op status side channel (self-disclosed §n.3) | Chain replay uses other agents' private ops, so the **existence** of a private update changes a shared item's status for another agent. leak_count = 0, and no content or code is exposed. | Must be fixed before multi-user use (ADR-6) |
| Visual brain | ARGUED only, and blocked until SPEC B4.3 is amended | P4.V capped at 5 |
| Real 2-process and kill durability, footprint, 100k | UNMEASURED | E1 scored one tier lower; K5 = 0; P8 ≤ 3 |

## F. Implementation blueprint (brief; FINAL/ compiles this)

1. **Port the prototype.** Port Spec-Y `adapter.py` (384 lines, stdlib only) to `one-for-all-api/ebrain/` as store, CLI and an MCP server. This is 2 days.
2. **Fix replay visibility.** Replay chains over the **viewer-visible** ops only (ADR-6), keeping the tests green.
3. **Gate healing.** Ship the heal loop behind a "propose only" flag until harm is attributed: demotions go to the e-brain Inbox for a human, not into autonomous effect (ADR-4).
4. **Integrations.** Add the Claude Code hooks, the Codex AGENTS.md block and the voice session pack (all J items ARGUED), then the Supabase replica with laptop-only fallback.
5. **Visual brain.** Build the `/e-brain` page after SPEC B4.3 is amended, fed by an export from the store. This is also the decisive experiment.
6. **Plan.** 9 developer-days, finishing by 8 Dec, before the 14 Dec freeze.

## G. ADRs

| ADR | Decision | Status | Measured basis |
|---|---|---|---|
| ADR-1 | Base the E-Brain on the Spec-Y fact-chain graph | **Provisional** (INCONCLUSIVE) | Highest Final 57.39 and highest MC 56.00 |
| ADR-2 | No model call on the query or write path; model steps batch-only under Claude Pro, with the rule as production fallback | Accepted | Every spec has query p95 ≤ 21 ms except Spec-X at 1029 ms; the voice budget is SPEC B5.1 |
| ADR-3 | Provenance: T3 quarantine, an `untrusted` render, authority from the envelope only, secrets redacted at ingest | **Accepted; beats Control measurably** | Injection 0 against Control's 0.483–0.667 in every run; poison and spoof classes 0 against 0.7–1.0 |
| ADR-4 | Self-heal demotion stays reversible (overlay plus rollback) and proposes to a human until harm is attributed | Accepted | Stale demotion 1.0 against Control's 0.09 (beats it), but harm 0.27–0.60 against Control's 0.09 (worse); rollback_exact = 1 everywhere |
| ADR-5 | Investigate Control's retriever as the recall layer under Spec-Y's chain replay | **Unproven** (not adopted) | Control's correct_version_acc beats every spec in every run (0.84 at 10k against ≤ 0.67). This needs an ablation: Spec-Y with Control's ranking, margin ≥ 0.02 on every seed, zombie and injection not regressed |
| ADR-6 | Chain replay restricted to the viewer's T8-visible ops (Spec-X's fold already does this) | Accepted (security) | Spec-Y §n.3 self-disclosure; T8; DQ1 risk in multi-user use |
| ADR-7 | Lineage status for restatements (a copy is never fresher than its origin) | Accepted, with a caveat | dup_item_rate 0 against Control's 0.014–0.026, and summary zombies 0.05–0.12 (mean) against Control's 0.85–1.0. It is only as good as chain resolution |

### Control rule analysis (§7.2)

- **Not triggered.** Control is disqualified under DQ2, and its MC (40.05) is below every spec's (48.45–56.00).
- **Not absorbed.** No team component goes into a Control-based winner, because there is none.

For the record, the measured head-to-head against Control on every run:

| | Metrics |
|---|---|
| The specs beat Control on | injection (all three), zombie_rate, dup_item_rate, tokens_mean (by 4–8×), stale_demotion_recall, summary_zombie_rate |
| Control beats the specs on | correct_version_acc (every run), heal_harm_rate at 10k, conflict_acc and asof_acc at 10k |

No ablation was run, so no component meets the §7.2 adoption test. ADR-5 records the candidate.

## Decisive next experiment (chosen mechanically, §7.5)

- **Prerequisite (§7.4a):** run the 2 missing sealed seeds at 1k and 10k for Spec-Y and Spec-Z.
- **Experiment:** measure **P4.V**. Render the Spec-Y and Spec-Z visual-brain pages, each fed by an export of its own prototype store at 10k, and verify V1–V10 by rendering.
- **Why this one:** it is the largest component that is not fully measured, at W = 0.72 Final points per point. Its maximum swing is 7.56, which is at least the 4.02 gap.
- **Pre-registered decision rule:** Spec-Z overtakes only if its measured V exceeds Spec-Y's by ≥ 5.6 points. Otherwise Spec-Y stays leader, and it becomes WINNER if its re-scored lead is > 5.00 on 3 sealed seeds with ARGUED credit removed.
