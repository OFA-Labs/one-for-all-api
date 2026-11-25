# E-Brain Tournament: Judge Scoring Anchors v1.0

Status: FROZEN on 2026-11-23 by the Chief Judge. It was written before any spec, exchange, round or orchestrator file was opened.
Applies to Spec-X, Spec-Y and Spec-Z (all blinded) and to Control.

These inputs, and no others, were used to write this file:
- `benchmark/INTERFACE.md` (benchmark contract v1, frozen 2026-11-23)
- `benchmark/harness/api.py` (`HARNESS_API_VERSION = "1.0.0"`)
- `kb/registry.md`
- `../one-for-all-web/docs/SPEC_ITERATION_1.md` (product context, cited below as SPEC)

These were not opened: `teams/`, `exchange/`, `rounds/`, `.orchestrator/` and `STATE.md`. At freeze, `benchmark/harness/` held only `api.py`. No generator, token counter or Control adapter existed yet, so the metric names below are those in INTERFACE §4.

Immutability: the Orchestrator records the sha256 of this file at freeze. After the judge opens any spec, this file does not change. If a case comes up that this file does not cover, the judge decides it by the most literal reading of this file and logs the decision and its reason in `judge/log.md`, which is append-only.

---

## 0. Conventions used by every section

### 0.1 Evidence tiers and factors

| Tier | Factor f | What qualifies |
|---|---|---|
| MEASURED | 1.0 | A value produced by the frozen harness on the reference laptop. Also a deterministic judge-run check whose command and output are kept in the judge log: a script, a test run, a page render, a line count or a path check. |
| REPRODUCED | 0.8 | The behaviour is shown by reading source code at cited lines without running it: the contender's own prototype or page code, or a KB clone at its pinned SHA. |
| ARGUED | 0.5 | Reasoning backed by real citations that were opened (permalinks at registry SHAs, papers, official docs) but not exercised on the contender's code. |
| CLAIMED | 0 | No evidence, or the supporting citation failed the audit as UNSUPPORTED (§6). |

### 0.2 Score arithmetic (all mechanical)

1. **Raw component score r (0–10).** For a scale (§0.4), interpolate linearly between the two neighbouring anchor points and clamp at the ends. A step table (P2.D, P8) is not interpolated. A checklist gives r as the sum of its item points, each already multiplied by its own f.
2. **Usefulness gate g.** Every lower-is-better or speed component is multiplied by `g(a) = min(1, a / 0.50)`, where `a` is the paired accuracy named in the component's row. A system that shows nothing gets no credit for being safe, clean or fast.
3. **Component score:** `s = r × g × f`. For checklists, f is already applied per item.
4. **Parameter score:** `P = Σ (share × s)`. The shares in each parameter sum to 1, and caps are applied after this sum. P lies in [0, 10] and is reported to 2 decimals.
5. **Final:** `Final = Σ_p (P_p × w_p) / 10`. The weights sum to 100, so Final lies in [0, 100] and is reported to 2 decimals. Every threshold comparison (the 5-point gap and the 10-point issue) uses the 2-decimal Final.
6. **Measured Composite (MC):** the same formula restricted to the components marked **H** below, which are derived from harness `results.csv`. `MC = 100 × Σ_c (W_c × s_c) / Σ_c (W_c × 10)`, where `W_c = w_p × share_c`. MC is used only in §7.

Weights: P1 Retrieval 15, P2 Tokens 10, P3 Latency 8, P4 Freshness and visual brain 12, P5 Self-heal 15, P6 Truthfulness 10, P7 Security 10, P8 Scalability 2, P9 Cost 5, P10 Integration and buildability 8, P11 Evidence quality 5.

### 0.3 Data and aggregation

- **Scoring runs:** every contender is run on the sealed championship seeds (at least 3) at sizes 1000 and 10000, on the reference laptop, with the frozen harness. Public seeds 101–103 are used only for the gate (§5), attacks (§4) and the corruption probe (§4.2).
- **Notation:** `m[Sx]` is metric m from the runs of scenario Sx. `@B` is token budget B, and `@10k` is size 10000. A component that names no size uses every size the harness reports for that scenario.
- **Aggregation across runs:** share metrics use the arithmetic mean over runs. Latency metrics use the median over seeds of the per-run value at 10k. Counts (`leak_count`, `acked_lost`, `budget_violations`) are summed. `rollback_exact` uses the mean.
- If the harness reports a metric only pooled, not per scenario, the pooled value is used for every contender.
- **UNMEASURED:** if the cause is the contender (timeout, crash or exception), the component scores 0. If the cause is that the harness cannot compute the metric for anyone, the component is dropped for all contenders and its share is spread proportionally over the parameter's other components. If a harness defect hit only some contenders, they are re-run, and if a re-run is impossible the component is dropped for all.
- **Latency** is scored only from runs on the reference laptop. Re-runs on other machines never feed P3 or P8.

### 0.4 Scales (all absolute; arrows show the better direction)

| Scale | Used for | 0 | 2 | 4 | 6 | 8 | 10 |
|---|---|---|---|---|---|---|---|
| ACC ↑ | correct_version_acc, conflict_acc, asof_acc | ≤ 0.40 | 0.55 | 0.70 | 0.80 | 0.90 | ≥ 0.97 |
| REC ↑ | ambiguous_recall, stale_demotion_recall, budget-restricted accuracy | ≤ 0.20 | 0.40 | 0.55 | 0.70 | 0.85 | ≥ 0.95 |
| ZOM ↓ | zombie_rate, dup_item_rate | ≥ 0.35 | 0.20 | 0.10 | 0.05 | 0.02 | 0.000 |
| HARM ↓ | heal_harm_rate | ≥ 0.20 | 0.10 | 0.06 | 0.03 | 0.01 | 0.000 |
| INJ ↓ | injection_success_rate | ≥ 0.30 | 0.15 | 0.07 | 0.03 | 0.01 | 0.000 |
| PROV ↑ | provenance_valid | ≤ 0.70 | 0.85 | 0.93 | 0.97 | 0.99 | ≥ 0.999 |
| TPC ↓ | proxy tokens per correct answer | ≥ 1000 | 700 | 450 | 250 | 120 | ≤ 60 |
| QP95 ↓ | query_p95_ms @10k | ≥ 1500 | 500 | 200 | 100 | 50 | ≤ 25 |
| QP50 ↓ | query_p50_ms @10k | ≥ 600 | 200 | 80 | 40 | 20 | ≤ 10 |
| WP95 ↓ | write_p95_ms @10k | ≥ 1000 | 300 | 100 | 40 | 15 | ≤ 5 |
| MP95 ↓ | maintain_p95_ms @10k | ≥ 180000 | 60000 | 15000 | 5000 | 2000 | ≤ 500 |

Interpolation example: correct_version_acc = 0.85 lies between 0.80 (score 6) and 0.90 (score 8), so r = 7.00.

**Absolute or relative to Control:** every anchor in this file is absolute. That keeps them pre-registered and independent of how Control turns out. Control is scored on the same absolute anchors (§3). Its relative role is limited to three things: the Control rule and the adoption margins in §7.2, and the Δ vs Control column on every scorecard row, which is for information only.

The latency scales follow from SPEC B5.1. A voice turn is targeted at 1.2 s median and 2.0 s p95 from the EU, so retrieval on that path must be a small share of it. A query p95 of 100 ms "fits" (score 6), and 1.5 s scores 0 because it alone exceeds the whole median turn.

### 0.5 Scorecard row (every score cites its tier and source)

`<contender> | <component> | raw value | source (results.csv run id + row, file:line, permalink, or judge-log entry) | tier | f | g | r | s | Δ vs Control`

---

## 1. Parameter anchors

### P1. Retrieval accuracy and context relevance (weight 15)

| Comp | Share | Input | Scale | Gate | H |
|---|---|---|---|---|---|
| A | 0.50 | mean(correct_version_acc[S1], [S3], [S7@10k]) | ACC | none | H |
| B | 0.25 | ambiguous_recall[S8] | REC | none | H |
| C | 0.25 | mean(correct_version_acc[S4], [S5], [S6], [S10]): accuracy under adversity | ACC | none | H |

Level guide (absolute):
- **10:** the current code is shown as current in ≥ 97% of canary queries, including at 10k and under adversity, and every expected chain is returned in ≥ 95% of ambiguous queries.
- **8:** about 90% and 85%.
- **6:** about 80% and 70%.
- **4:** about 70% and 55%.
- **2:** about 55% and 40%.
- **0:** ≤ 40% and ≤ 20%.

### P2. Token efficiency (weight 10)

| Comp | Share | Input | Scale | Gate | H |
|---|---|---|---|---|---|
| A | 0.40 | mean(correct_version_acc[S9@64], [S9@256]) | REC | none | H |
| B | 0.30 | TPC = tokens_mean[S9@1024] / max(correct_version_acc[S9@1024], 0.05) | TPC | none (TPC already penalises low accuracy) | H |
| C | 0.20 | dup_item_rate[S3] | ZOM | g(correct_version_acc[S3]) | H |
| D | 0.10 | budget_violations ÷ bundles, over all runs | step: 0 → 10; ≤ 0.001 → 5; otherwise 0 | g(pooled correct_version_acc) | H |

Level guide:
- **10:** ≥ 95% accuracy at 64 and 256 tokens, ≤ 60 proxy tokens per correct answer, no duplicates, no violations.
- **6:** about 70% at tight budgets and about 250 tokens per correct answer.
- **2:** about 40% at tight budgets, about 700 tokens per correct answer, or many duplicates.
- **0:** context is useless under a budget.

### P3. Retrieval and update latency (weight 8)

| Comp | Share | Input (reference laptop, @10k) | Scale | H |
|---|---|---|---|---|
| A | 0.45 | effective query_p95_ms | QP95 | H |
| B | 0.20 | effective query_p50_ms | QP50 | H |
| C | 0.20 | effective write_p95_ms | WP95 | H |
| D | 0.15 | effective maintain_p95_ms | MP95 | H |

Gate: the whole parameter is multiplied by `g(correct_version_acc[S7@10k])`.

**Effective latency** is the measured prototype value plus, for each model or network step that the real design runs synchronously on that call:
- the spec's declared p95 for the step;
- at least 400 ms for each remote model call and at least 20 ms for each local model inference, unless a MEASURED figure for that step exists;
- 2000 ms if the spec declares no latency for the step.

A step is treated as synchronous unless the spec says it is asynchronous and the prototype's call path agrees. Steps that run inside `maintain()` add their declared latency multiplied by the calls per maintain at 10k. Declared figures are applied at face value with no tier discount, because they can only lower the score (§2, rule T-e). An attack can replace them with evidence-backed figures.

Level guide:
- **10:** retrieval cannot be noticed in a voice turn (p95 ≤ 25 ms).
- **6:** fits the voice budget comfortably (p95 ≤ 100 ms).
- **2:** a noticeable delay (p95 about 500 ms).
- **0:** breaks the turn targets (≥ 1.5 s).

### P4. Freshness and visual-brain usability (weight 12)

| Comp | Share | Input | Scale or points | Gate | H |
|---|---|---|---|---|---|
| F | 0.40 | zombie_rate[S1] (silent updates left current) | ZOM | g(correct_version_acc[S1]) | H |
| V | 0.60 | Visual-brain checklist V1–V10 below, 1 point each × f | points | none | no |

| Item | 1 point when |
|---|---|
| V1 | The page mounts on the existing `e-brain` route of `one-for-all-web` (SPEC B4.3) and names the route file and the read API it calls. |
| V2 | All six statuses (current, superseded, conflicted, stale, quarantined, unknown) look distinct, are not told apart by colour alone, and have a legend. |
| V3 | Each fact has a version timeline: value code, ts, agent, authority, what it superseded, and silent updates marked as such. |
| V4 | Provenance drill-down goes from an item to its `source_op_ids` and the original write text, and `external` items carry a visible "untrusted" badge. |
| V5 | A conflict and quarantine inbox, where a human resolve action (pick, confirm or reject) creates an `authority="human"` write. |
| V6 | A self-heal log lists every `maintain()` action (action, targets, reason) with one-click undo, through `rollback` or a compensating write. |
| V7 | Filters by project, agent, kind and status, plus subject search, and the viewer sees only what T8 allows them to see. |
| V8 | Freshness and usage signals: age, last confirmed, and followed and ignored counts from `observe()`. |
| V9 | Usable at 10k memories through aggregation or pagination. It is MEASURED only if a rendered page loads a 10k export in ≤ 2 s on the reference laptop. |
| V10 | Works at 390 px width with no horizontal scroll, can be used from the keyboard, and sits inside the website's shared shell. |

The tier of each V item is set as follows:
- **MEASURED:** the judge renders a working page, fed by an export from the contender's own prototype store, and sees the item.
- **REPRODUCED:** the item is present in page source that the judge reads but cannot render.
- **ARGUED:** a wireframe or mockup together with the data contract (the fields and the API).
- **CLAIMED:** the item is only mentioned.

Level guide for V:
- **10:** a working page, with all ten items verified by rendering.
- **8:** a working page that misses about two items.
- **6:** a partly working page, or a complete specification with some code.
- **4:** a complete wireframe and data contract for eight or more items (8 × 0.5 = 4).
- **2:** a few items specified.
- **0:** no visual brain.

### P5. Autonomous self-healing quality (weight 15)

| Comp | Share | Input | Scale | Gate | H |
|---|---|---|---|---|---|
| A | 0.40 | stale_demotion_recall[H] | REC | none | H |
| B | 0.35 | heal_harm_rate[H] | HARM | g_H = min(1, stale_demotion_recall / 0.50) | H |
| C | 0.15 | zombie_rate[S10] (wrong summaries left current) | ZOM | g(correct_version_acc[S10]) | H |
| D | 0.10 | rollback_exact[S11], mean over runs | r = 10 × mean | none | H |

By construction, a no-op `maintain()` scores at most 0.15 × 10 + 0.10 × 10 = 2.5.

Level guide:
- **10:** demotes ≥ 95% of stale memories, harms none, never lets a wrong summary be current, and is fully reversible.
- **8:** about 85% demoted and about 1% harmed.
- **6:** about 70% demoted and about 3% harmed.
- **4:** about 55% demoted and about 6% harmed.
- **2:** about 40% demoted or about 10% harmed.
- **0:** no effective healing, or harmful healing.

Unrecoverable harm is a disqualifier (§4.1, DQ3).

### P6. Truthfulness, provenance and version correctness (weight 10)

| Comp | Share | Input | Scale or points | Gate | H |
|---|---|---|---|---|---|
| A | 0.25 | mean(zombie_rate[S4], [S7@10k]) (tombstones and scale) | ZOM | g(mean correct_version_acc[S4], [S7@10k]) | H |
| B | 0.25 | conflict_acc[S2] (T4 and T5) | ACC | none | H |
| C | 0.15 | provenance_valid (all runs) | PROV | g(pooled correct_version_acc) | H |
| D | 0.20 | asof_acc[S11] | ACC | none | H |
| E | 0.15 | Integrity checklist below | points | none | H |

The integrity checklist has three items:
- **E1 (5 points):** `acked_lost` = 0 in every run, including S2 with two processes and the S5 kill.
- **E2 (3 points):** no crash or uncaught exception in any run, including S4 dangling `supersedes` and S5 malformed writes.
- **E3 (2 points):** every malformed S5 write and every reuse of an op_id with different text is rejected (`accepted=False`). If ≥ 90% are rejected, E3 earns 1 point.

**Cap:** if `acked_lost` > 0 in any run, P6 is capped at 3.0.

Level guide:
- **10:** no zombies, conflicts resolved ≥ 97% as §2 requires, ≥ 99.9% valid provenance, ≥ 97% as-of accuracy, and no data lost.
- **6:** about 5% zombies, about 80% conflicts, about 97% provenance and about 80% as-of accuracy.
- **2:** about 20% zombies or about 55% conflicts.
- **0:** version answers cannot be trusted.

### P7. Security and agent isolation (weight 10)

Precondition: `leak_count` = 0 (§4.1, DQ1).

| Comp | Share | Input | Scale or points | Gate | H |
|---|---|---|---|---|---|
| A | 0.50 | injection_success_rate[S6] | INJ | g(correct_version_acc[S6]) | H |
| B | 0.20 | S6 by class: 2.5 points for each class with success ≤ 0.02. The classes are imperative payload, poison code, `supersedes` hijack and authority spoof in text. | points | g(correct_version_acc[S6]) | H |
| C | 0.30 | Isolation checklist for the real design, X1–X5 below, 2 points each × f | points | none | no |

If neither the harness nor its per-query log gives a per-class breakdown, B equals A.

| Item | 2 points when |
|---|---|
| X1 | The T8 filter (project, plus shared-or-same-agent) is applied inside the storage query before ranking and truncation, not as a post-filter. |
| X2 | `agent_id` and `authority` come from the caller's credential or channel and never from write text. `human` authority can only come from a human UI action. |
| X3 | Provenance is fixed at ingestion. External text is rendered as quoted data with `untrusted`, never placed where an instruction would go in `rendered`, and never promoted over a first-party value. |
| X4 | Each ONE FOR ALL member is a tenant above project level, and Delete-my-data removes that user's memories, derived summaries and visual-brain caches within 24 h (SPEC J10 and B11.3). |
| X5 | Secrets (keys, tokens, passwords, one-time codes) are rejected or redacted before they are stored, and they never appear in the visual brain or in exports. |

Level guide:
- **10:** no attack succeeds in any class, and isolation is enforced at the store and shown in code that runs.
- **6:** about 3% of attacks succeed, and isolation is argued concretely.
- **2:** about 15% succeed.
- **0:** ≥ 30% succeed. Note that ≥ 20% is a disqualifier anyway (DQ2).

### P8. Scalability (weight 2)

This is a step table and every level is cumulative: a level requires its own conditions and all the conditions below it. Inputs:
- acc_n is correct_version_acc pooled over all canary queries at size n.
- p95_n is query_p95_ms at size n.
- T_n is the contender's wall time for a full run at size n, taking the maximum over seeds.

| Level | Conditions |
|---|---|
| 0 | The 10k run times out or crashes. |
| 2 | The 10k run completes, possibly with non-timeout UNMEASURED metrics. |
| 4 | T_10k < 15 min, acc_10k ≥ acc_1k − 0.12, p95_10k ≤ 15 × p95_1k |
| 6 | acc_10k ≥ acc_1k − 0.06, p95_10k ≤ 6 × p95_1k |
| 8 | T_10k < 5 min, acc_10k ≥ acc_1k − 0.03, p95_10k ≤ 3 × p95_1k |
| 10 | The 100k run completes within budget, acc_100k ≥ acc_10k − 0.03, p95_100k ≤ 3 × p95_10k |

Odd scores: a contender scores L + 1 when it holds every condition of level L and at least one condition of level L + 2. Gate: × g(acc_10k). H. If the 100k run is executed for no one, level 10 is unattainable for everyone.

### P9. Operational and infrastructure cost (weight 5)

This is a checklist of five items, 2 points each × f. The reference load is 3 writing agents, 300 writes a day, 1,000 queries a day, 24 `maintain()` calls a day, and 10k memories.

| Item | 2 points when |
|---|---|
| K1 | The MVP runs on a CPU-only Windows laptop with no paid service other than Claude Pro. |
| K2 | Every model step declares its calls per day and tokens per call at the reference load, and runs inside Claude Pro (for example a Claude Code session or headless run) or on a free tier whose terms allow the data. Memory that holds browser page content or personal facts never goes to a free provider that may train on it or have humans review it (SPEC B7.10). A design with no model step meets K2. |
| K3 | Every external dependency names a paid option and a free fallback that really exists (cited), or there are no external dependencies. |
| K4 | The ONE FOR ALL cloud backend (SPEC B7.1, EU server) reaches the brain at $0 extra, for example inside `one-for-all-core` or through the free Supabase Postgres in SPEC C1 row 6, with a stated fallback for free-tier pausing. |
| K5 | Footprint, measured by the judge: the workdir after the 10k run is ≤ 100 MB (2 points) or ≤ 500 MB (1 point). MEASURED. |

Level guide:
- **10:** every item verified by measurement or code.
- **6:** a laptop-only MVP whose costs and fallbacks are argued.
- **2:** costs undeclared, or paid APIs required.
- **0:** the design needs paid infrastructure beyond Claude Pro, or sends private memory to free providers.

### P10. Integration with ONE FOR ALL and buildability in the window (weight 8)

This checklist totals 10 points. Tiers: an item is MEASURED when a working stub or test is exercised by the judge, REPRODUCED when the code is present and read, and ARGUED when the spec gives concrete `existing:` paths and interfaces.

| Item | Points | Criterion |
|---|---|---|
| J1 | 1 | Says where the brain of record lives (the laptop or the EU server), how the other side reads and writes it, and what happens when that side is offline. Claude Code and Codex run on the laptop, and the voice agent runs on the server (SPEC B7.1). |
| J2 | 1 | Claude Code: named read and write mechanisms (a hook, an MCP server, or memory-file sync) on `existing:` paths. |
| J3 | 1 | Codex: named read and write mechanisms on `existing:` paths. |
| J4 | 1 | The ONE FOR ALL voice agent and backend: a named call site, with retrieval either off the voice critical path or at a measured p95 ≤ 150 ms. Answers from the ask budget are stored as facts (SPEC B6.7). |
| J5 | 1 | The visual brain is mounted on the existing `e-brain` route (SPEC B4.3) through a read API that enforces T8. |
| J6 | 2 | Prototype size: lines that are not blank and do not start with `#`, over every `.py` file under `prototype/` except `tests/`, docstrings included. ≤ 700 lines earns 2 points and 701–1000 earns 1 (INTERFACE §1). MEASURED. |
| J7 | 1 | Python-first: the core is Python, and the real design adds at most 2 third-party packages, each free and each with a stdlib or `sqlite3` fallback. |
| J8 | 1 | A dated plan that fits between 23 Nov and 14 Dec 2026 (the feature freeze in SPEC B14.1), with ≤ 10 developer-days of total E-Brain effort and an explicit cut line. |
| J9 | 1 | Bootstrap: starts on an empty store and imports the existing memory files (`CLAUDE.md`, `AGENTS.md` and the Claude Code auto-memory `MEMORY.md`) without manual editing. |

Level guide:
- **10:** every integration works and is tested, the prototype is ≤ 700 lines, and the plan fits.
- **6:** concrete argued integrations, a small prototype and a plan that fits. For example 5 × 0.5 + 2 + 0.8 + 0.5 + 0.5 = 6.3.
- **2:** vague integrations or an oversized prototype.
- **0:** cannot be integrated or cannot be built by one developer in the window.

### P11. Quality and reproducibility of evidence (weight 5)

These items are the judge's own observations, so every item takes f = 1.0. The checklist has five items of 2 points each.

| Item | 2 points when |
|---|---|
| Q1 | Every number the spec labels MEASURED traces to a `results.csv` row that records contender, code hash, seed, size and harness version, and the judge's re-run reproduces it. Deterministic metrics must match exactly, and latency within ±30% on the reference laptop. 100% earns 2 points and ≥ 80% earns 1. |
| Q2 | Permalink audit (§6): no errors of any kind in the sample earns 2 points. Only MINOR errors, in ≤ 10% of the sample, earns 1. |
| Q3 | Tier labelling: the 20 claims are drawn as follows. Candidates are the sentences that contain a tier label. The seed is the audit seed + 2, and if fewer than 20 candidates exist, all are used. The label counts as matching when the spec's own label equals the judge's classification. Mismatches are counted as under-claims + 2 × over-claims. ≥ 90% matching earns 2 points and ≥ 75% earns 1. |
| Q4 | The team's own tests pass and cover each of T1–T8 with at least one test. All 8 rules earn 2 points and ≥ 5 earn 1. |
| Q5 | One documented command reproduces every MEASURED number from a clean copy. 2 points if it works as documented, and 1 point if it works after at most 2 trivial path or command edits. |

Level guide:
- **10:** every result is re-run and matches, citations are clean, labels are honest, and tests cover every rule.
- **6:** most results reproduce, with minor citation or label slips.
- **2:** results cannot be re-run.
- **0:** no reproducible evidence.

---

## 2. How an evidence tier scales a score

**Rule: multiplicative, applied per component or checklist item, never as a cap.** The formula is `s = r × g × f(tier)`. The result is that MEASURED can reach 10, REPRODUCED at most 8, ARGUED at most 5 and CLAIMED 0. A parameter supported only at ARGUED tier is therefore worth at most 5.

How a tier is assigned:
- **T-a.** A component takes the highest tier at which that specific value is supported for this contender's design.
- **T-b.** Lower-tier evidence never overrides a higher-tier measurement of the same quantity. An argument that the real system would beat the measured prototype earns nothing. A MEASURED counter-result replaces an argued value.
- **T-c.** Evidence about another system (KB-01 to KB-04, papers, products) supports a contender's design at ARGUED at most, because it is not the contender's code.
- **T-d. Simulated model steps** (INTERFACE §1):
  - The harness value of a deterministic stand-in counts as MEASURED for the design if the spec ships that rule as the production fallback.
  - If the rule is only a stand-in, every component whose call path reaches it takes f = 0.8.
  - If an attack shows that the stand-in uses information production would not have (ground truth, generator internals, or subject lists or templates copied from the generator), those components take f = 0.5 until they are re-measured without that information.
- **T-e.** Penalties are never discounted. A team's own declared latency, cost or limitation applies at face value.
- **T-f.** Audit outcomes (§6): MISCITED drops the claim one tier, UNSUPPORTED makes it CLAIMED, and FABRICATED disqualifies.

**Worked example 1 (a checklist, P4).**
- V1 is verified in page source the judge could not render, so it is REPRODUCED: 0.8.
- V2–V6 are given as a wireframe with a data contract, so they are ARGUED: 5 × 0.5 = 2.5.
- V7–V10 are absent: 0.
- The total is V = 3.3.
- zombie_rate[S1] is 0.03 with correct_version_acc[S1] = 0.88. That gives r_F = 8 − 2 × (0.01 / 0.03) = 7.33, g = 1, f = 1, so F = 7.33.
- The result is P4 = 0.4 × 7.33 + 0.6 × 3.3 = 4.91, which contributes 4.91 × 12 / 10 = 5.90 Final points.

**Worked example 2 (a stand-in, P5.A).**
- stale_demotion_recall is 0.80, so r = 6 + 2 × (0.10 / 0.15) = 7.33.
- If the spec ships the rule as the production fallback, s = 7.33.
- If production instead uses a Claude step with no rule fallback, s = 7.33 × 0.8 = 5.87.

---

## 3. How Control is scored

- Control is `benchmark/control/adapter.py`. The same harness, seeds, sizes, machine, anchors and tiers apply to it as to every team.
- Control does not go through the qualification gate. It has no spec, so it earns no ARGUED credit. Its evidence is the harness (MEASURED) and the judge's reading of its code (REPRODUCED).
- A checklist item that Control does not provide scores 0. An item that is met when nothing is needed, such as K2 "no model step" or K3 "no external dependencies", is credited at REPRODUCED when Control's code confirms it.
- In P11, Q2 and Q3 do not apply. P11 for Control is (Q1 + Q4 + Q5 points) × 10 / 6, and Q1 is judged by re-running Control and comparing with its own `results.csv`.
- The disqualifier checks (§4.1) apply to Control. If Control trips one, the judge reports it to the Orchestrator as a harness or Control defect, and Control leaves both the ranking and the Control rule.
- Attacks on Control count only at MEASURED or REPRODUCED tier. The judge adjudicates them against Control's code, and Control has no defence.
- Control is ranked together with the teams (§7.3) and is also tested by the Control rule (§7.2). Δ vs Control is reported on every scorecard row.

---

## 4. Disqualifiers, attacks, deductions and kills

### 4.1 Disqualifiers

Disqualifiers are mechanical. Once scoring has started there is no fix cycle. Leaks found at the gate are covered in §5.

- **DQ1, leakage.** Either of:
  - `leak_count` > 0 in any harness run of the version being scored;
  - an unrefuted MEASURED or REPRODUCED attack showing cross-agent (private), cross-project or cross-user exposure in the prototype, or in the real design as written (citing the spec's text). Exposure through `rendered`, item text, the visual brain or a maintain report all count.
- **DQ2, unmitigated memory poisoning.** Any of:
  - aggregated injection_success_rate[S6] ≥ 0.20;
  - ≥ 0.50 success within any single S6 attack class;
  - an unrefuted MEASURED or REPRODUCED attack in which an external or spoofed write becomes `current` over a first-party value, without `untrusted`, and stays current after `maintain()`, in ≥ 50% of at least 10 trials.
- **DQ3, unrecoverable autonomous corruption.** The corruption probe (§4.2) fails, or a new `Adapter(workdir)` cannot reopen the store after `maintain()`.
- **DQ4, fabrication.** Any FABRICATED citation or any fabricated benchmark result (§6).

### 4.2 Corruption probe

This is a judge script run against the adapter API only, so its result is MEASURED. It runs on public seed 101 and on the first sealed seed, both at size 1000.

1. Let t0 be the ts of the write at the 60th percentile of the stream.
2. Run A, in a fresh workdir:
   1. Write every write with ts ≤ t0.
   2. Record P0, the codes shown `current` for every canary query at t0 with budget 1024.
   3. Write the rest of the stream and `observe()` all H traces.
   4. Call `maintain(t_end)` three times.
   5. Call `rollback(t0)`.
   6. Record P1 with the same queries at ts = t0.
3. Run B is identical to run A except that it makes no `maintain()` calls. It produces P1_B.
4. **The probe fails** in either case:
   - Some code c that the ground truth marks current at t0 satisfies c ∈ P0, c ∉ P1 and c ∈ P1_B. The difference between runs A and B shows the loss came from `maintain()`.
   - `rollback` raises, and `maintain()` turned a code that the ground truth marks current at t_end from current to not current.

### 4.3 Attacks

- **Record:** id, target, the components it affects, the claim, the proposed new raw value or the checklist items it voids, the evidence, and the tier. An attack that names no value is applied at the anchor level whose description matches the failure it demonstrates.
- **Attack tiers:**
  - MEASURED: a reproducible harness run or a failing test against the contender's prototype.
  - REPRODUCED: a code path in the prototype, or the spec's own text, that produces the failure when read literally.
  - ARGUED: reasoning with real citations.
  - CLAIMED: an assertion with no evidence. It never deducts.
- **Refuted** means the defence brings evidence at or above the attack's tier showing the attack's evidence is wrong. A fix counts only when the protocol allows a revision at that point and the revised prototype is re-run, at which point the revised version becomes the version being scored. An argument cannot refute a MEASURED attack.
- An attack that is not refuted **stands**.

### 4.4 How a standing attack becomes a deduction

- `Δ = f(attack tier) × (Final_before − Final_rescored)`, where Final_rescored re-scores the affected components with the attack's value. No parameter goes below 0.
- Standing attacks are applied together. Each parameter is re-scored once, with all of them taken into account, so the joint deduction is never more than the sum of the individual ones.
- An issue that no component covers goes to the parameter whose name covers it, and is re-scored at the level-guide description that matches what was demonstrated. For example, "cannot be built in the window" sets P10 to 2.
- An ARGUED attack on a disqualifier does not disqualify. It is converted into a deduction by this rule.

**Example.** An ARGUED attack says the real LLM summariser would restate superseded codes, and moves P5.C from 9 to 4. The raw change is 5 × 0.15 = 0.75 P5 points. That is 0.75 × 15 / 10 = 1.125 Final points, and with f(ARGUED) = 0.5 the deduction is 0.56. This is not a kill.

### 4.5 A "10+ point issue" and KILL

A 10+ point issue is a single standing attack, or a group of standing attacks that share one root cause (they cite the same prototype function or the same spec section), whose tier-scaled deduction Δ is at least 10.00 normalised Final points.

A contender is **KILLED** in either case:
- a 10+ point issue stands;
- a MEASURED or REPRODUCED attack on DQ1, DQ2 or DQ3 stands.

Unrelated smaller attacks reduce the score but never kill, even when their sum is 10 or more.

---

## 5. Qualification gate for each spec_v1

| # | Check | How it is checked (results go in the judge log) |
|---|---|---|
| G1 | Sections a–p of the protocol's spec template are present and substantive. | Each letter has a heading, plus at least one checkable statement: a mechanism, a number, a path, a citation or a decision. "TBD", placeholder text, or "N/A" without a one-line reason fails. |
| G2 | The spec is evidenced. | Every load-bearing claim carries a tier label. Every mechanism has at least one citation, or at least one prototype file:line. Permalinks use the registry format `https://github.com/<owner>/<repo>/blob/<sha>/<path>#L<a>-L<b>`. |
| G3 | The design is technically plausible. | (a) It does not contradict INTERFACE §1: standard library only, deterministic, no network, durable `workdir`, two processes sharing one workdir. (b) Every model step in the real design names its deterministic stand-in, cost, latency and the metrics it drives. (c) It needs nothing outside a laptop, free tiers and Claude Pro. (d) Each rule T1–T8 maps to a named mechanism. |
| G4 | The reference prototype exists and keeps to the contract. | `teams/<team>/prototype/adapter.py` defines `Adapter` with a `name` attribute and `Adapter(workdir, config=None)`, and `isinstance(Adapter(tmp), AdapterProtocol)` is true. An AST scan of the imports must find only `sys.stdlib_module_names` plus the prototype's own modules. It must find none of these modules: `socket`, `ssl`, `http`, `urllib`, `ftplib`, `smtplib`, `poplib`, `imaplib`, `xmlrpc`, `webbrowser`. It must find none of these calls: `time.time`, `time.time_ns`, `time.monotonic`, `time.perf_counter`, `datetime.now`, `datetime.utcnow`, `datetime.today`, `date.today`, unseeded `random` or `random.Random()`, `os.urandom`, `uuid1` or `uuid4`, `secrets`. A flagged call passes only if the judge's reading confirms it cannot affect stored state or output. |
| G5 | The prototype's own tests pass. | From the `ebrain-tournament` folder, `benchmark\.venv\Scripts\python.exe -m pytest teams\<team>\prototype\tests -q -p no:cacheprovider` must exit 0, with at least 1 test collected and no failures or errors. |
| G6 | Harness smoke run (only if the harness exists at gate time; otherwise skipped for every spec and logged). | Public seed 101 at size 1000 is run twice in fresh workdirs. Both runs must finish within 15 minutes with no crash, the deterministic metrics must be identical across the two runs, and `leak_count` must be 0. |
| G7 | Integration paths are `existing:` paths. | Every integration point is written as `existing:<path>`, where the path is absolute or relative to `voice-agents/`, and resolves when the judge runs a glob. A file the design will create is accepted only as `new:<path>` whose parent directory is an `existing:` path. |
| G8 | Permalink audit (§6) on spec_v1. | No FABRICATED verdicts. |

Outcomes:
- **QUALIFIED:** every check passes.
- Any failure other than G8, including a leak seen in G6, gives the team **one fix cycle** with an itemised list of the failed checks. The resubmission is checked again in full. Any failure on that second check means **NOT QUALIFIED**.
- A G8 failure means **DISQUALIFIED** at once (DQ4), with no fix cycle.

The judge opens specs only after this file's hash has been recorded.

---

## 6. Permalink and result audit

**Population.**
- The distinct permalinks in a spec, and in any submission file the spec links to, are collected with the regex `https://github\.com/[^/\s]+/[^/\s]+/blob/[0-9a-f]{7,40}/[^\s#)\]]+#L\d+(-L\d+)?`.
- Trailing `.,;:)]>` is stripped, `#La` is read as `#La-La`, and duplicates are removed. The count is N.
- Other citations (URLs, arXiv IDs, DOIs) form a second population, counted as N_B.

**Sample size per spec.**
- From the permalinks: `n = min(N, max(20, ceil(0.25 × N)))`.
- From the other citations: `n_B = min(N_B, max(5, ceil(0.25 × N_B)))`.
- Also audited, in full: every permalink cited by an attack or a defence that could cause a KILL or a deduction of 2 or more Final points.

**Seed rule.** It is run with `benchmark\.venv\Scripts\python.exe` (Python 3.11):
```
H = sorted(sha256(bytes of the delivered file).hexdigest() for each of Spec-X, Spec-Y, Spec-Z)
seed = int(sha256(("EBRAIN-AUDIT-v1|" + label + "|" + "|".join(H)).encode()).hexdigest()[:16], 16)
sample   = random.Random(seed).sample(sorted(permalinks), n)
sample_B = random.Random(seed + 1).sample(sorted(other_citations), n_B)
```
The label is `Spec-X`, `Spec-Y` or `Spec-Z`. The seed depends on all three frozen specs, so no single team can predict it or grind it. During a fix cycle, the resubmitted file's bytes replace the original's. If fewer than three specs were delivered, H uses those that were.

**Checking each permalink.** The audit uses local clones in `kb/sources/<folder>/`, choosing the folder whose `git remote get-url origin` equals the registry URL. Only read-only git commands are used. Nothing from a clone is run, built or imported.

1. **Registry.** If `owner/repo` is not in the registry (rows KB-01 to KB-04 or Discovered sources), check whether the commit exists with `gh api repos/<o>/<r>/commits/<sha>`. If it exists, mark the citation **OFF-REGISTRY**, which counts as MISCITED. If it does not exist, it is FABRICATED.
2. **Commit.** `git -C <clone> cat-file -t <sha>` must return `commit`. If it does not, the citation is FABRICATED. If the commit exists but is not the registry pin, mark it **OFF-PIN** (counts as MISCITED) and keep checking at the cited sha.
3. **Path.** If `git -C <clone> show <sha>:<path>` fails, look for exactly one file at that sha with the same basename that passes step 4. If one exists, the citation is MISCITED. Otherwise it is FABRICATED.
4. **Lines.** Read lines a..b and the window [a−15, b+15]. If a is beyond the end of the file + 15, the citation is FABRICATED. Otherwise the verdict depends on what the citing text attributes to those lines:

| What the citing text attributes to the lines | OK | MINOR | MISCITED | UNSUPPORTED | FABRICATED |
|---|---|---|---|---|---|
| A verbatim code quote of 12 or more characters, or a code block (whitespace-normalised search) | found in a..b | found in the window | found elsewhere in the file, or found in the repo with `git grep -F` | n/a | found nowhere in the repo at that sha |
| Identifiers in backticks in the citing sentence | at least one in a..b, and the behaviour is supported | found in the window and supported | supported only elsewhere in the file | identifiers present but behaviour not supported | none of the identifiers anywhere in the repo at that sha |
| Prose only | the lines support the claim | the window supports it | n/a | not supported | (only through steps 1–3) |

**Other citations.**
- **OK:** the source opens and supports the claim.
- **INACCESSIBLE:** the source cannot be opened. The claim becomes CLAIMED, and this is not fabrication.
- **UNSUPPORTED:** the source opens but does not support the claim.
- **FABRICATED:** the identifier never existed, for example an arXiv ID or DOI that does not resolve, or a verbatim quotation in quotation marks is absent from a source that opens.

**Fabrication versus a minor error.**
- **FABRICATED** is only the mechanical cases above, and it disqualifies the spec (DQ4).
- **MINOR** is a line-offset error of ≤ 15 lines. The claim keeps its credit, and the error counts only in Q2.
- **MISCITED**, **OFF-PIN** and **OFF-REGISTRY** drop the claim one tier.
- **UNSUPPORTED** sets the claim to CLAIMED.

If a sample contains 3 or more UNSUPPORTED or MISCITED verdicts, the judge audits every permalink in that spec. Each verdict in the full audit is applied on its own, and none of them disqualifies unless it is FABRICATED.

**Benchmark-result audit (6.5).**
- A number labelled MEASURED must cite a `results.csv` row or a run log that records contender, code hash, seed, size and harness version. If it cites none, it becomes CLAIMED.
- The judge re-runs the cited run three times. **FABRICATED result**, which is DQ4: the code hash, seed, size and harness version all match, the three re-runs agree with each other, and a deterministic (non-`_ms`) metric still differs from the reported value.
- If the re-runs disagree with each other, the prototype is nondeterministic. The claim becomes CLAIMED and a G4 violation is logged, but there is no disqualification.
- If the code hash differs, the result is stale. The claim becomes CLAIMED, with no disqualification.
- If the median latency of the re-runs is more than 2 × the reported latency, the result is **MISREPORTED**. The measured value replaces it and it counts against Q1, with no disqualification.

Every verdict is recorded in `judge/audit_<label>.md` as: permalink, citing sentence, verdict, the lines seen, and the commands run.

---

## 7. Selection, the Control rule, INCONCLUSIVE and tie-breaks

### 7.1 Order of operations

1. Apply the disqualifiers (§4.1) and mark contenders DISQUALIFIED.
2. Adjudicate attacks (§4.3–4.5) and mark contenders KILLED or apply deductions.
3. Compute Final and MC for every survivor, Control included.
4. Apply the Control rule (§7.2).
5. Rank and apply the 5-point gap test (§7.3).
6. Run the evidence-sufficiency test (§7.4).
7. Break ties (§7.6).

### 7.2 The Control rule (evaluated before the normal ranking)

The rule triggers when Control survives and MC(Control) is strictly greater than MC(t) for every surviving team t. Equal MC does not trigger it. When it triggers, the outcome is **CONTROL+**: Control plus only the team components that pass the tests below.

- **A mechanism on the harness call path** passes only with a MEASURED ablation: Control plus that component, run on every scored seed. On every seed it must improve its target metric over Control by at least the margin, regress no other metric by more than the same margin, and trip no disqualifier. The margins are 0.02 absolute for shares, 10% for tokens and 20% for latency.
- **A feature off the harness path**, such as the visual-brain page or an integration adapter, passes when it is verified at MEASURED tier and touches no harness call.
- Each adopted component gets an ADR: context, decision, the ablation rows, and consequences.
- A component without such evidence is listed as "unproven", together with the experiment that would decide it.
- Components from a DISQUALIFIED team are never adopted. Components from a KILLED team are adopted only if they are not implicated in the killing issue.
- If no team survives, the outcome is CONTROL+ under the same adoption rule.

### 7.3 Ranking and INCONCLUSIVE

- Rank the survivors, Control included, by Final.
- Let G = Final(1st) − Final(2nd). **If G ≤ 5.00, the result is INCONCLUSIVE.** The judge names the leader, meaning the higher Final, with ties broken by §7.6, and names one decisive experiment (§7.5).

### 7.4 Evidence sufficiency (no empirical winner on insufficient evidence)

A WINNER is declared only if both conditions hold:
- **(a)** Every contender has complete scoring runs, with no UNMEASURED results caused by the contender, on at least 3 sealed seeds at both sizes, and at most 10% of the Final weight sits in components dropped for everyone.
- **(b)** When both top Finals are recomputed with ARGUED credit set to 0 (keeping only MEASURED and REPRODUCED), the leader still leads by more than 5.00.

If either condition fails, the result is INCONCLUSIVE, with the Final leader named.

### 7.5 The decisive experiment (chosen mechanically)

- L is the leader and R the runner-up. W_c is the Final weight of component or item c.
- The candidates are the components or items where f_L,c < 1 or f_R,c < 1, and whose maximum swing `W_c × ((10 − s_R,c) + s_L,c)` is at least G.
- Choose the candidate with the largest `W_c × |r_L,c − r_R,c|`. Break ties by larger W_c, then by lower parameter number.
- If no component qualifies, the experiment is to re-run every scenario on 5 extra sealed seeds and re-score the component with the largest `W_c × |s_L,c − s_R,c|`.

The experiment is published with what to run, on whom and for which metric or check. It also carries a pre-registered decision rule: the result value at which the order flips.

### 7.6 Tie-break

Ties are exact equality of the 2-decimal Final, or the need to name a leader under INCONCLUSIVE. They are broken in this order:
1. higher MC;
2. higher P7;
3. higher P5;
4. higher P1;
5. smaller J6 line count.

If every step ties, the contenders are declared **co-leaders**, with no winner and with the decisive experiment from §7.5.
