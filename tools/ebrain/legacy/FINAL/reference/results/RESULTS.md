# Reference results: MEASURED on synthetic PUBLIC seeds only (harness 1.0.0, run 2026-11-23)

**Command** (from `benchmark\`): `.\.venv\Scripts\python.exe -m harness.runner --contender <dir> --size <1000|10000> --seed <s> --out ..\FINAL\reference\results\<file>.csv`

**Raw rows** are in `public_1k.csv` and `public_10k_101.csv`. These CSVs feed `ebrain/limits_facts.json` through `python -m ebrain.facts`, and test T-024 re-checks it.

## Contenders

| Label | Dir | Code hash (harness) | Config |
|---|---|---|---|
| v2 frozen | `teams/gamma/prototype` | cb925a7aedb4103a | tournament v2 |
| ref default | `FINAL/reference/impl` (`adapter.py` glue → `ebrain/store.py`) | 080aff1ae40ac42f | F1 viewer replay, heal `propose`, join `off` |
| ref heal_auto | `FINAL/reference/variants/heal_auto` | ff6d48a5f95f5275 | F1, heal `auto`, join `off` |
| ref join_on | `FINAL/reference/variants/join_on_heal_auto` | fd045c8af0468eb3 | F1, heal `auto`, join `on` (0.70 / 0.45) |
| ref join_low | `FINAL/reference/variants/join_on_low_threshold` | 908b2ee44097820b | F1, heal `auto`, join `on` (0.50 / 0.35) |

The variant hashes cover only each wrapper folder. Every variant imports `FINAL/reference/impl/ebrain/store.py`, which is covered by the ref default hash 080aff1ae40ac42f.

## 1k, public seeds 101 / 102 / 103

| Metric | v2 | ref default | heal_auto, join_on, join_low |
|---|---|---|---|
| correct_version_acc | 0.931 / 0.917 / 0.875 | 0.931 / 0.917 / 0.875 | identical to v2 |
| zombie_rate | 0.103 / 0.217 / 0.250 | 0.121 / 0.217 / 0.250 | identical to v2 |
| stale_demotion_recall | 1 / 1 / 1 | 0.33 / 0 / 0 (proposals only, by design) | 1 / 1 / 1 |
| heal_harm_rate | 0.17 / 0.33 / 0.33 | same | same |
| conflict_acc | 0.67 / 0.67 / 1.00 | same | same |
| asof_acc | 0.92 / 0.92 / 1.00 | same | same |
| ambiguous_recall | 1 / 1 / 1 | same | same |
| injection, leak_count, acked_lost | 0 | 0 | 0 |
| rollback_exact | 1 | 1 | 1 |
| query_p95_ms | 1.4–2.4 | 1.8–2.6 | 1.5–3.5 |

## 10k, public seed 101

| Metric | v2 | ref default | heal_auto | join_on | join_low |
|---|---|---|---|---|---|
| correct_version_acc | 0.6742 | 0.6742 | 0.6758 | 0.6758 | 0.6709 |
| zombie_rate | 0.5907 | 0.5971 | 0.5923 | 0.5923 | 0.5971 |
| ambiguous_recall | 0.133 | 0.200 | 0.200 | 0.200 | 0.200 |
| conflict_acc | 0.450 | 0.467 | 0.467 | 0.467 | 0.450 |
| asof_acc | 0.696 | 0.704 | 0.704 | 0.704 | 0.704 |
| stale_demotion_recall | 1.0 | 0.733 | 1.0 | 1.0 | 1.0 |
| heal_harm_rate | 0.833 | 0.800 | 0.800 | 0.800 | 0.867 |
| query_p95_ms | 24.8 | 27.4 | 28.4 | 29.2 | 25.2 |
| injection, leak_count, acked_lost | 0 | 0 | 0 | 0 | 0 |

**Run-to-run noise (measured).** The unchanged v2 code (hash cb925a7aedb4103a) was run at 10k seed 101 three times on 2026-11-23:

| Metric | Run values |
|---|---|
| zombie_rate | 0.5939, 0.5923, 0.5907 |
| conflict_acc | 0.450, 0.467, 0.450 |

Every 10k difference in the table above is inside this spread. The 1k runs repeated identically.

## Review band (`review_band_pairs.txt`, produced by `count_pairs.py`)

Precision is judged against the generator's sealed chain ids. This is measurement only; the store never sees them.

| Size / seed | Pairs at 0.70 / 0.45 (default) | True same | Pairs at 0.50 / 0.35 | True same |
|---|---|---|---|---|
| 1k / 101 | 0 | 0 | 5 | 3 |
| 1k / 102 | 1 | 1 | 14 | 10 |
| 1k / 103 | 4 | 2 | 9 | 5 |
| 10k / 101 | 39 | 14 (0.36) | 126 | 40 (0.32) |

## Reading (plain)

1. **The experimental subject join did not help.**
   - At 1k it changed nothing.
   - At 10k its zombie change (+0.002 vs the latest v2 run) is inside the noise.
   - The low-threshold variant is not better (zombie 0.5971, acc 0.6709).
   - **It stays OFF; T-042 fails.**
2. **The F1 viewer-scoped replay (privacy fix)** produced no measurable metric change. It is kept for privacy (ADR-6), not for accuracy.
3. **Default `propose` healing** applies nothing without a human, so stale_demotion_recall drops (0.33/0/0 at 1k, 0.73 at 10k). At 1k seed 101 zombie_rate rises from 0.103 to 0.121, because the stale memory stays current until approved. That is the price of zero autonomous demotions.
