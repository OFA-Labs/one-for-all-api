# RE-SCORE v2: all three sealed seeds (this section supersedes the parameter tables below)

Runs: sealed seeds 556920, 878791 and 235664, each at 1k and 10k. Public seed 101 is excluded because anchors §0.3 says public seeds are not scoring runs. Source: `benchmark/results_v2.csv`, recomputed by `judge/tools/score.py`, with output in `judge/tools/score_out.txt`.

The checklist inputs V, X, K, J, Q and E are unchanged. The per-class injection input P7.B was recomputed from the harness for Spec-Z: every class now has a mean ≤ 0.02, and the imperative class stays at REPRODUCED, giving 9.5 (was 7.0).

| Parameter (w) | Control | Spec-X | Spec-Y | Spec-Z |
|---|---|---|---|---|
| P1 Retrieval (15) | 6.80 | 0.00 | 4.72 | 3.55 |
| P2 Tokens (10) | 5.52 | 0.00 | 8.20 | 7.54 |
| P3 Latency (8) | 7.33 | 0.00 | 8.78 | 9.54 |
| P4 Freshness and visual brain (12) | 0.00 | 3.00 | 3.00 | 2.75 |
| P5 Self-heal (15) | 1.27 | 0.00 | 5.00 | 5.11 |
| P6 Truthfulness (10) | 5.25 | 1.35 | 5.06 | 4.53 |
| P7 Security (10) | 0.50 | 2.04 | 9.04 | 8.11 |
| P8 Scalability (2) | 4 | 0 | 3 | 3 |
| P9 Cost (5) | 5.20 | 5.00 | 5.00 | 5.00 |
| P10 Integration and build (8) | 2.80 | 6.30 | 6.30 | 6.30 |
| P11 Evidence (5) | 6.67 | 8.00 | 8.00 | 8.00 |
| **Final / 100** | **38.21 (DQ2)** | **18.53** | **59.64** | **56.23** |
| MC | 41.83 | 1.88 | 59.14 | 54.90 |
| Final with ARGUED credit set to 0 | 38.21 | 10.03 | 51.14 | 48.09 |

**Spec-X.** Its 10k runs timed out at 900 s on sealed seeds 878791 and 235664 (`run_status UNMEASURED (timeout)`). Under §0.3 that is caused by the contender, so every component that needs a 10k run scores 0, and P8 = 0 because the 10k run timed out. This is a scored failure, not a disqualifier.

**Disqualifier re-check over the 6 sealed runs:**

| Check | Control | Spec-X | Spec-Y | Spec-Z |
|---|---|---|---|---|
| leak_count | 0 | 0 | 0 | 0 |
| injection (mean) | **0.594: DQ2 stands** | 0 | 0 | 0.008 |
| worst class | poison 1.0, spoof 1.0 | — | — | poison 0.10 (< 0.50) |
| acked_lost, crashes | 0 | 0 | 0 | 0 |

**Spec-Z DQ3 check.** Spec-Z `rollback_exact_maintain` = 0 at 10k on seed 235664, with 14 of 15 probes equal. The judge ran the §4.2 intent check with `judge/tools/rb_diag.py`, a harness replay that does not change the harness.

- In the one differing probe, the ground-truth head `VC-58SSZF` is still `current` after the rollback.
- The only difference is that a non-head item, `VC-AF36RE`, dropped out of the bundle.
- So no ground-truth-current code was lost, and DQ3 is not triggered. The issue is rollback inexactness.

The P5.D input is `rollback_exact`, which equals 1 in all six runs, so P5.D is unchanged.

**Sufficiency check (§7.4):**
- (a) There are now 3 sealed seeds at both sizes. Read literally, (a) still fails, because Spec-X has contender-caused timeouts. That does not matter here, because (b) and §7.3 also fail.
- (b) With ARGUED credit removed, the lead is 51.14 − 48.09 = **3.05**, which is not more than 5.

---

# E-Brain Tournament: Scorecard (Chief Judge)

Scored on 2026-11-23 with `judge/anchors.md` v1.0, frozen with sha256 `CC7FDCB1589D7AC4D31542B6CAE2C7EBA492D0E9A0DAB08EECB521E5DC418AFF`. The version scored is v2 of each spec and prototype. Labels stay blinded.

The arithmetic is mechanical. `judge/tools/score.py` computes it from `benchmark/results_v2.csv` and prints every component. `judge/tools/audit.py` makes the seeded permalink sample, and its output is in `judge/tools/audit_out.txt`.

Contender to code hash (from `results_v2.csv`, matching the defence records):

| Contender | Code hash |
|---|---|
| Control | `860e0c34a43f8f21` |
| Spec-X | `f0f368cdb55c8f50` |
| Spec-Y | `cb925a7aedb4103a` |
| Spec-Z | `f38c3148d9351b6f` |

## 0. Deviations from the anchors (Orchestrator's lean plan) and how each was scored

| Anchor rule | What happened | Treatment |
|---|---|---|
| §0.3: at least 3 sealed seeds at both sizes | Three runs exist: 1k at the sealed seed (556920), 10k at seed 101, and 10k at the sealed seed. | Scores use these 3 runs. §7.4(a) fails, so no empirical WINNER can be declared (verdict §A). |
| §6: n = max(20, 25%) | n = 8 per spec, as the Orchestrator directed. | 24 permalinks audited, 0 errors. Q2 is scored on this sample. |
| §5: judge gate | The Orchestrator ran a mechanical gate: sections a–p present, `existing:` paths resolve, tests pass. | Accepted, and G1–G8 were not repeated. G8 is covered by the audit below. |
| P1.C: correct_version_acc for S4 and S5 | Not reported. | Dropped for everyone. P1.C is the mean of S6 and S10. |
| P2.B: tokens_mean at S9@1024 | Only the pooled `tokens_mean` was reported. | The pooled value is used for everyone, as §0.3 allows. |
| P6.A: zombie rate for S4 | Reported as `tombstone_zombie_rate`. | Used as the S4 zombie rate. The S4 accuracy gate was dropped, so the S7@10k gate is used. |
| P6.E1: acked_lost under real 2-process and kill tests | UNMEASURED. The harness ran 2 instances in one process, plus a reopen. | E1 is scored one tier lower: 5 × 0.8 = 4.0, for everyone. P6.E = 4 + 3 + 2 = 9.0. |
| P7.B: per-class injection | Hijack, poison and spoof are reported. The imperative class is not. | The imperative class is inferred as 0 where aggregate injection is 0 in every run (MEASURED: Spec-X and Spec-Y). For Spec-Z (aggregate 0.033 at 10k on seed 101) it is credited at REPRODUCED, from the code gate, as 2.0. |
| P8 level 10 (100k run) | Not run. | Level 10 is unattainable for everyone. |
| P9.K5 footprint | Not measured. | 0 for everyone. |
| P11.Q3: 20-claim tier sample | Not sampled, under the lean plan. | Q3 = 1 for every spec. Each had a v1 §h "supersedes hijack: REPRODUCED" over-claim that a MEASURED attack refuted (round record). |
| P11.Q4: T1–T8 test coverage | Tests pass (Orchestrator), but the test files are sealed. | Coverage is CLAIMED only, so Q4 = 1 for every spec. Control ships no tests the judge saw, so Q4 = 0. |
| DQ3 corruption probe | The bespoke two-run probe was not run. | The harness S11 `rollback_exact` (periodic `maintain()` after t_r, then rollback) and `rollback_exact_maintain` measure the same property: rollback after `maintain()` restores the recorded status map exactly. `store_reopen_ok` covers reopening. |

Latency was measured with 4 runs in parallel on one laptop. The conditions were the same for every contender.

## 1. Disqualifier checks (all MEASURED; source `results_v2.csv`, 3 runs)

| Check | Threshold | Control | Spec-X | Spec-Y | Spec-Z |
|---|---|---|---|---|---|
| DQ1 leak_count, in every run, plus S6 leak probes | > 0 | 0 | 0 | 0 | 0 |
| DQ2 injection_success_rate (mean, max) | ≥ 0.20 | **0.556, 0.667** | 0, 0 | 0, 0 | 0.011, 0.033 |
| DQ2 worst single class, max over runs | ≥ 0.50 | **poison 1.0, spoof 1.0** | 0 | 0 | poison 0.10 |
| DQ3 rollback_exact and rollback_exact_maintain, store_reopen_ok | any 0 | 1, 1 | 1, 1 | 1, 1 | 1, 1 |
| DQ4 fabricated citation (audit, §4) | any | none (no citations) | 0 / 8 | 0 / 8 | 0 / 8 |
| DQ4 fabricated result (judge re-run, §5) | mismatch | matches | matches | matches | matches |
| **Status** | | **DISQUALIFIED (DQ2)** | qualified | qualified | qualified |

Control is excluded from both the ranking and the Control rule (anchors §3). Its scores below are reported for reference only. Even before the disqualification, Control's MC (40.05) is below every spec's MC, so the Control rule would not trigger in any case.

## 2. Per-parameter scores

P is the parameter score (0–10, 2 decimals) and w its weight. MC is the harness-only composite.

| Parameter (w) | Control | Spec-X | Spec-Y | Spec-Z | Tier of the main evidence |
|---|---|---|---|---|---|
| P1 Retrieval (15) | 5.74 | 2.87 | 3.54 | 3.06 | MEASURED |
| P2 Tokens (10) | 5.52 | 7.73 | 7.57 | 6.85 | MEASURED (P2.B uses pooled tokens_mean) |
| P3 Latency (8) | 8.95 | 4.23 | 9.80 | 9.95 | MEASURED, at 10k with 4 parallel runs |
| P4 Freshness and visual brain (12) | 0.00 | 3.00 | 3.00 | 2.70 | F: MEASURED. V: ARGUED (×0.5) |
| P5 Self-heal (15) | 1.16 | 5.00 | 5.00 | 5.05 | MEASURED |
| P6 Truthfulness (10) | 4.63 | 4.27 | 4.38 | 3.63 | MEASURED. E1 one tier lower |
| P7 Security (10) | 0.50 | 9.04 | 9.04 | 7.38 | A, B: MEASURED. C: REPRODUCED or ARGUED |
| P8 Scalability (2) | 3.00 | 3.00 | 3.00 | 3.00 | MEASURED (step table) |
| P9 Cost (5) | 5.20 | 5.00 | 5.00 | 5.00 | checklist; MEASURED, REPRODUCED or ARGUED |
| P10 Integration and build (8) | 2.80 | 6.30 | 6.30 | 6.30 | checklist; J6 MEASURED, others ARGUED |
| P11 Evidence (5) | 6.67 | 8.00 | 8.00 | 8.00 | judge checks (f = 1) |
| **Final / 100** | **36.93 (DQ)** | **51.97** | **57.39** | **53.37** | |
| **MC (harness only)** | 40.05 | 48.45 | 56.00 | 50.90 | |
| Final with ARGUED credit set to 0 (§7.4b) | 36.93 | 43.47 | 48.89 | 45.23 | |

### 2.1 Component detail (s = r × g × f; inputs averaged over the 3 runs, latency the median of the two 10k runs)

Raw inputs are in `judge/results_summary.md`. Values in parentheses are the inputs.

| Component | Control | Spec-X | Spec-Y | Spec-Z |
|---|---|---|---|---|
| P1.A ACC(mean S1, S3, S7@10k) | 6.86 | 3.37 | 4.74 | 3.30 |
| P1.B REC(ambiguous_recall) | 1.22 | 0.00 | 1.00 | 2.30 |
| P1.C ACC(mean S6, S10) | 8.00 | 4.73 | 3.70 | 3.34 |
| P2.A REC(S9 @64 and @256) | 5.51 | 5.07 | 5.60 | 4.02 |
| P2.B TPC (pooled tokens / acc@1024) | 3.46 (≈ 488 / 0.94) | 9.00 (≈ 58 / 0.65) | 7.78 | 7.48 |
| P2.C ZOM(dup S3) × g | 6.38 | 10 | 10 | 10 |
| P2.D budget violations | 10 | 10 | 10 | 10 |
| P3.A QP95@10k | 8.72 (41 ms) | 0.94 (1029 ms) | 10 (21 ms) | 10 (19 ms) |
| P3.B QP50@10k | 7.62 | 1.54 (291 ms) | 9.84 | 10 |
| P3.C WP95@10k | 10 | 10 | 9.15 (9.2 ms) | 9.76 |
| P3.D MP95@10k | 10 | 10 | 10 | 10 |
| P4.F ZOM(zombie S1) × g | 0 (0.92) | 0 (0.43) | 0 (0.52) | 0 (0.42) |
| P4.V visual checklist | 0 | 5.0 (V1–V10 at ARGUED) | 5.0 (V1–V10 at ARGUED) | 4.5 (V1–V9 at ARGUED; V10 only mentioned, so CLAIMED) |
| P5.A REC(stale_demotion_recall) | 0 (0.09) | 10 (1.0) | 10 (1.0) | 10 (0.96) |
| P5.B HARM(heal_harm) × g_H | 0.45 (0.09) | 0 (0.27) | 0 (0.60) | 0 (0.50) |
| P5.C ZOM(zombie S10) × g | 0 | 0 (0.43) | 0 (0.55) | 0.32 (0.33) |
| P5.D rollback_exact | 10 | 10 | 10 | 10 |
| P6.A ZOM(mean of S4 tombstone and S7@10k zombie) × g | 0 | 1.00 | 0.97 | 1.10 |
| P6.B ACC(conflict_acc) | 3.56 (0.67) | 1.78 (0.53) | 2.00 (0.55) | 0 (0.38) |
| P6.C PROV × g | 10 | 10 | 10 | 10 |
| P6.D ACC(asof_acc) | 4.46 (0.72) | 3.63 (0.67) | 3.94 (0.70) | 2.53 (0.59) |
| P6.E integrity | 9.0 | 9.0 | 9.0 | 9.0 |
| P7.A INJ × g | 0 | 10 | 10 | 7.89 |
| P7.B per-class | 2.5 (hijack only) | 10 | 10 | 7.0 (poison 0.033 fails) |
| P7.C isolation checklist | 0 | 6.8 | 6.8 | 6.8 |
| P8 step level | 3 | 3 | 3 | 3 |

How the P8 step level was reached for each contender:

| Contender | acc_1k → acc_10k (drop) | T_10k | p95 ratio | Level |
|---|---|---|---|---|
| Spec-X | 0.891 → 0.641 (0.25) | 796 s | 15.0 | 3: fails level 4 on the drop and the ratio, meets T < 15 min |
| Spec-Y | drop 0.20 | 36 s | 13.5 | 3: level 2, plus one level-4 condition |
| Spec-Z | drop 0.34 | 31 s | 7.0 | 3: level 2, plus one level-4 condition |
| Control | drop 0.125 | 61 s | 9.9 | 3: level 2, plus one level-4 condition |

### 2.2 Checklist evidence (judge reading)

**P7.C isolation.** Every spec scores X1 1.6, X2 1.0, X3 1.6, X4 1.0, X5 1.6, for a total of 6.8.

| Item | Spec-X | Spec-Y | Spec-Z | Tier |
|---|---|---|---|---|
| X1: T8 filter in SQL before ranking | `(vis='shared' OR agent=?)` in SQL at adapter.py L266 and L349 | the same at L303 | `VISIBLE` at L44 | REPRODUCED |
| X3: external content kept as data | UNTRUSTED tag at L397 | at L355 | `untrusted:"…"` at L404 | REPRODUCED |
| X5: secrets redacted before storage | `REDACT` at L167 | `SECRET_RE` at L158 | at L209 | REPRODUCED |
| X2 (channel identity) and X4 (user tenancy, Delete-my-data) | design text only | design text only | design text only | ARGUED |

Control's T8 filter is a Python post-filter at L342 and it has no redaction. Its "never override" claim is contradicted by measured poison and spoof success, so Control's isolation checklist is 0.

**P9 cost.** Every spec scores 5.0:

| Item | Points | Basis |
|---|---|---|
| K1 | 2.0 | stdlib core MEASURED in the harness |
| K2, K3, K4 | 1.0 each | model steps declared and run under Claude Pro headless; Supabase free tier with a local fallback (ARGUED) |
| K5 | 0 | not measured |

Every model step is batch or asynchronous and off the harness path, and the rule ships as the production fallback, so rule T-d gives f = 1 for the metrics.

Control scores 5.2: K1 2.0 (MEASURED), K2 1.6 (no model step, REPRODUCED), K3 1.6 (no dependencies, REPRODUCED), K4 0, K5 0.

**P10 integration and build.** Every spec scores 6.3: J1–J5 0.5 each (ARGUED, concrete `existing:` paths), J6 2.0, J7 0.8 (stdlib core, REPRODUCED), J8 0.5 and J9 0.5 (ARGUED).

| Contender | J6 lines | Plan |
|---|---|---|
| Spec-X | 467 | 9 days, ends 8 Dec |
| Spec-Y | 384 | 9 days, ends 8 Dec, and the e-brain page waits on a B4.3 amendment |
| Spec-Z | 454 | 9 days, ends 11 Dec |

Control scores 2.8: J6 2.0 (472 lines) and J7 0.8.

**P11 evidence.** Every spec scores 8.0. Q1 = 2: the judge re-ran each v2 prototype at 1k on seed 101, and correct_version_acc, zombie_rate, conflict_acc, asof_acc, injection and heal_harm match the specs' tables exactly (X 0.9828 / 0.2241, Y 0.931 / 0.1034, Z 0.9655 / 0.1034). Q2 = 2, Q3 = 1, Q4 = 1, and Q5 = 2 (the documented runner command works).

Control scores 6.67: its re-run at 1k on the sealed seed matches `results_v2.csv` exactly, and (Q1 2 + Q4 0 + Q5 2) × 10 / 6 = 6.67.

## 3. Attacks (one kill round, against v1) and their status in v2

| # | Target | Attack (by) | Tier | v2 status | Deduction |
|---|---|---|---|---|---|
| 1 | Spec-Y | An external `supersedes` hijack with a new path becomes current; seed 102 hijack class 0.5 (Spec-X G1, Spec-Z G1) | MEASURED | Fixed (rule order). Refuted by MEASURED results: hijack 0 in all 3 scored runs, and 0 in the judge re-run on seed 101. | 0 |
| 2 | Spec-Y | T5 stale-base write shown current (Spec-X G2) | MEASURED | Partly fixed. conflict_acc_t5 on scored runs is 0.33, 0.43 and 0.67; P6.B already reflects this. | 0 (priced in) |
| 3 | Spec-Y | Predictions disproved (Spec-Z G2) | MEASURED | Conceded. Priced into P4.F, P5.B and P5.C. | 0 |
| 4 | Spec-X | A cue word alone demotes a correct memory (Spec-Y A1) | MEASURED | Fixed. Defender re-ran it at MEASURED tier and the judge's 1k re-run matches. heal_harm in P5.B is already 0. | 0 |
| 5 | Spec-X | A cross-chain `supersedes` erases a human decision (Spec-Y A2, Spec-Z A1) | MEASURED | Fixed. Defender re-ran it at MEASURED tier. | 0 |
| 6 | Spec-X | S10 summary zombies (Spec-Z A2) | MEASURED | Conceded. P5.C = 0. | 0 (priced in) |
| 7 | Spec-Z | A merge heal erases an unrelated fact (Spec-X B1, Spec-Y A3) | MEASURED | Fixed with the `_fusion_ok` blast radius. Defender re-ran it at MEASURED tier. | 0 |
| 8 | Spec-Z | Five predictions fail at 10k (Spec-X B2) | MEASURED | Conceded. The sealed 10k values are what was scored in P1, P6 and P8. | 0 (priced in) |
| 9 | Spec-Z | One shared term crosses subjects (Spec-Y A4) | MEASURED | Fixed. Defender re-ran it at MEASURED tier. | 0 |

**Kill claims:** none stands. Every disqualifier attack (#1, #4, #5, #7) was refuted by measured v2 behaviour. Every 10k-collapse attack (#3, #6, #8) is already in Final, because Final uses the sealed MEASURED values the attacks predicted, so Δ = 0 (anchors §4.4). No contender is KILLED.

Note: the blinded round record has label typos ("Spec-Spec-Y", and a Spec-Y section headed "Spec-Z author"). The judge mapped every attack and defence by code hash.

## 4. Permalink audit (n = 8 per spec, seed per anchors §6 over the v1 sha256s, verified with read-only git in `kb/sources/` at the registry pins)

The population for each spec is the GitHub permalinks in its v2 file plus its primary ledger (Spec-X: P7, Spec-Y: T5, Spec-Z: R2).

| Spec | N | Seed | Result |
|---|---|---|---|
| Spec-X | 169 | 6900668410346330544 | 8 OK, 0 errors |
| Spec-Y | 111 | 497540842346583540 | 8 OK, 0 errors |
| Spec-Z | 113 | 10508268828411092061 | 8 OK, 0 errors |

All 24 citations use the pinned SHA, the path exists, and the claimed content is in the cited range.

| Spec | Permalink (repo: path#lines) | What is in the cited lines | Verdict |
|---|---|---|---|
| X | engram: internal/cli/exchangehash.go#L76-L110 | `compareExchangeHashes` checks the `xh1:` prefix | OK |
| X | engram: docs/specs/technical/vault-write-lock.md#L32-L39 | `.luhmann.lock` taken at command entry | OK |
| X | remcycle: src/dream/memory.py#L650-L656 | `_past` keeps statement, provenance, said_at, replaced_at | OK |
| X | remcycle: src/dream/memory.py#L335-L365 | `note_threads` opens and closes threads | OK |
| X | engram: dev/eval/LEDGER.md#L49 | "PPR improves retrieval": refuted | OK |
| X | remcycle: src/dream/reconcile.py#L112-L133 | `_home` slot aliasing | OK |
| X | claude-mnemonic: internal/worker/service.go#L1192-L1201 | deletes an observation when the LLM says invalid | OK |
| X | gbrain: src/core/cycle.ts#L169-L174 | "Never DELETE — facts stay as audit trail" | OK |
| Y | remcycle: src/dream/memory.py#L40-L42 | `_THREAD_LIFE = timedelta(days=14)` | OK |
| Y | remcycle: src/dream/archive.py#L346-L413 | FTS search over `turns` | OK |
| Y | remcycle: src/dream/reconcile.py#L136-L153 | `_decide`: add, reject, confirm or supersede | OK |
| Y | gbrain: src/schema.sql#L181-L278 | `generation` trigger and `page_generation_clock_seq` | OK |
| Y | gbrain: src/core/link-extraction.ts#L1319-L1348 | regex link-type inference with zero LLM calls | OK |
| Y | remcycle: docs/intent.md#L87 | the quote "Plain BM25 beat the graph and vector…" is verbatim | OK |
| Y | engram: internal/auto/prompts/place.txt#L14-L20 | a lesson supersedes only its own claim | OK |
| Y | engram: internal/auto/prompts/judge.txt#L12-L55 | lesson rubric, `covered` | OK |
| Z | engram: internal/luhmann/luhmann.go#L44-L121 | ID segment ordering and `ParseID` | OK |
| Z | remcycle: src/dream/memory.py#L172-L179 | `_hold` withholds an entry | OK |
| Z | claude-mnemonic: internal/scoring/calculator.go#L30-L100 | scoring formula and `CalculateComponents` | OK |
| Z | remcycle: src/dream/mirror.py#L62-L100 | `stage` copy and `_finish_accept` | OK |
| Z | remcycle: src/dream/daily.py#L15-L62 | `DUE_AFTER = timedelta(hours=20)` | OK |
| Z | engram: internal/cli/exchangehash.go#L91-L131 | `exchangeHash` canonical sha256 | OK |
| Z | engram: internal/auto/judge.go#L87-L122 | all 7 quoted constants are present | OK |
| Z | gbrain: src/core/facts/classify.ts#L1-L20 | contradiction classifier with a cosine fast path | OK |

## 5. Judge re-runs (benchmark-result audit)

The judge ran `benchmark/.venv/Scripts/python.exe -m harness.runner --size 1000 --seed 101` on `judge/blind/code/Spec-{X,Y,Z}` and on Control at the sealed seed. Output: `C:\Users\jaiva\AppData\Local\Temp\claude\dec757e8868ee089\6ae523ec-a81d-4dfb-b41e-59bb6e4402df\scratchpad\judge_rerun.csv` and `judge_rerun_ctl.csv` in the same folder.

Every deterministic metric checked equals the number the spec reported (Appendix D of Spec-X, Appendix C of Spec-Y, Appendix C of Spec-Z) and the matching `results_v2.csv` row for Control. No result was fabricated.

Code hashes differ from the reported ones only because the blinded folder holds `adapter.py` alone, without the tests.
