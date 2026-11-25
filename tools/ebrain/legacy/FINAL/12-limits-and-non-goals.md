# 12 Limits and non-goals

## 1. What "1k memories" means

| Term | Definition |
|---|---|
| memory | **one accepted write** (`WriteAck.accepted = true`) in one project of one user. Every version of a fact counts. So do copies, summaries, notes, logs and tombstones. A rejected or duplicate resend does not count. |
| chain | all versions of one fact. A chain with 5 versions is 5 memories. |
| counted by | `SELECT COUNT(*) FROM ops WHERE user_id=? AND project=?` (`Store.memory_count`) |

**Worked example of 1,000 memories.** This is the benchmark's 1k mix (INTERFACE §3): 150 spec versions, 200 code-file versions, 50 skill versions, 200 log entries, 200 agent claims, 50 decisions, 50 dependency notes, 50 tasks and 50 summaries. Together they hold about 50 tracked facts of 2–30 versions each, across 3 agents and 2 projects.

**How fast it fills.**

| Load | 1,000 memories in |
|---|---|
| The judge's reference load (3 agents, 300 writes/day) | about 3.3 days |
| A small project that stores only durable notes (3 agents × about 13 notes/day ≈ 40/day) | about 25 days, several weeks |

Not storing raw logs (20% of the mix) stretches it by a quarter.

## 2. Capacity behaviour

| Memories | `capacity_state` | Behaviour |
|---|---|---|
| ≤ 800 (`capacity_soft`) | `ok` | normal |
| 801–1000 (`capacity_hard`) | `near_limit` | normal; the UI meter turns amber |
| > 1000 | `beyond_tested_range` | **keeps working**. Every bundle item carries `beyond_tested_range`, the rendered header says "beyond tested range", the API response has `capacity_state`, and the UI shows the red state and notice. It is never silent. With `capacity_mode=reject`, writes get HTTP 507 instead. |

## 3. Measured numbers (synthetic benchmark only; Spec-Y v2 code, `benchmark/results_v2.csv`)

| Metric | 1k, 3 sealed seeds | 10k, 3 sealed seeds + public 101 |
|---|---|---|
| correct_version_acc | 0.844 / 0.918 / 0.951 | 0.618–0.673 |
| zombie_rate (old value still shown current) | 0.082 / 0.180 / 0.281 | 0.560–0.651 |
| conflict_acc | 0.50 / 0.67 / 1.00 | 0.47–0.68 |
| asof_acc | 0.75 / 0.92 / 1.00 | 0.63–0.70 |
| ambiguous_recall | 0.50 / 1.00 / 1.00 | 0.07–0.27 |
| heal_harm_rate (auto heal) | 0.00 / 0.17 / 0.17 | 0.73–0.83 |
| injection_success_rate, leak_count, acked_lost | 0, 0, 0 | 0, 0, 0 |
| rollback_exact | 1 | 1 |
| query p95 | 1.6–2.4 ms | 20.6–42.7 ms |

**Even at 1k it is not perfect.** In 5–16% of fact questions the current value is missing, and in 8–28% an outdated value is still shown as current.

## 4. Non-goals for this build

| Non-goal | Reason |
|---|---|
| More than 1,000 memories per project with stated reliability | measured accuracy drops to 0.62–0.67 at 10k |
| A Supabase replica or multi-device sync | unmeasured; the voice agent runs without memory when the laptop is offline |
| Embeddings, vector search or a reranker | ADR table in 11 |
| Any model call on the write or query path | ADR-2 |
| Automatic self-heal by default | ADR-4 |
| Automatic merging of possibly-same chains | ADR-9 |
| Encryption at rest | 06 |
| Real (non-synthetic) accuracy numbers | none exist yet; every number here comes from synthetic seeds |

## 5. Untested (stated as `# UNTESTED:` in code)

| Mechanism | Settling test |
|---|---|
| `_trigram_cosine` precision on real agent notes | T-041 extended with a labelled real-pair set |
| `_hybrid_join` effect | T-042 (currently fails: Δ = 0.000) |
| `_counter_evidence` harm attribution | T-031 per-action harm audit |
| Power-loss durability with `synchronous=NORMAL` | none in this build (06) |
