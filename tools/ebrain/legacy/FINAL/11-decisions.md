# 11 Decisions (ADRs)

**Sources.** The KB repos are pinned in `kb/registry.md`. The ledger IDs refer to `exchange/ledger_gamma.md` (T5-). Code lives in `FINAL/reference/impl/ebrain/` (store.py, models.py, api.py, facts.py).

**Measured basis.** "Measured" means the synthetic benchmark: `judge/results_summary.md` for sealed seeds and `FINAL/reference/results/` for public seeds.

| ADR | Decision | Status | Basis |
|---|---|---|---|
| ADR-1 | Base E-Brain on the Spec-Y versioned fact-chain graph (append-only ops, replay-derived status) | Provisional (judge: INCONCLUSIVE, leader Spec-Y 59.64 vs 56.23) | `judge/verdict.md` |
| ADR-2 | No model call on the write or query path; optional model steps are batch-only under Claude Pro, and the rule is the production fallback; none is enabled in this build | Accepted | query p95 1.6–2.4 ms at 1k and 20.6–42.7 ms at 10k (sealed) |
| ADR-3 | Provenance: T3 quarantine, an `untrusted` render, authority from the envelope only, secrets redacted at ingest | Accepted | injection 0 in every run vs Control 0.48–0.67 |
| ADR-4 | Self-heal defaults to `propose`; `auto` only by explicit config | Accepted | harm 0.00–0.17 at 1k and 0.73–0.83 at 10k; kill-round script s3 wrong demotion |
| ADR-5 | Control's retriever as the recall layer | Unproven, not adopted | Control acc 0.84–0.97 beats Spec-Y. This needs an ablation with margin ≥ 0.02 on every seed (judge ADR-5) |
| ADR-6 | Replay only viewer-visible ops | Accepted; implemented (F1) | judge ADR-6; T-010. No measurable metric effect: 1k identical to v2; at 10k seed 101 every difference is within the 0.003 zombie and 0.017 conflict run-to-run spread of unchanged v2 code |
| ADR-7 | Lineage status for restatements | Accepted, caveat: only as good as chain resolution | dup_item_rate 0; summary zombies 0.05–0.25 |
| ADR-8 | Capacity limits soft 800 / hard 1000 with a non-silent `beyond_tested_range` | Accepted | sealed acc 0.84–0.95 at 1k vs 0.62–0.67 at 10k |
| ADR-9 | EXPERIMENTAL hybrid subject join (token + char trigram) with a human review band | Implemented, **OFF by default** | no change at 1k; at 10k a +0.002 zombie change, which is within noise; 0.50 not better; review precision 0.36 at 10k |
| ADR-10 | A visual brain on `/e-brain`, which requires amending SPEC B4.3 | Accepted (user request) | 07-ui.md |

### ADR-9 re-run (M6, 2026-11-24): T-042 on the shipped store — still FAIL, join stays OFF

Re-ran the ablation with the harness on the **shipped** `one-for-all-api/ebrain/store.py`
through a temporary adapter that overrides `heal_mode=auto` and toggles
`subject_join` (baseline OFF vs join ON). Commands were the 09-test-plan T-042
commands, run from `benchmark\` with `.\.venv\Scripts\python.exe -m harness.runner
--contender <adapter> --size <size> --seed <seed> --out <csv>`. All eight raw CSVs
are in `FINAL/reference/results/t042_shipped_*.csv`.

| Size / seed | baseline zombie / acc (join OFF) | join ON zombie / acc | Δ zombie | Δ acc |
|---|---|---|---|---|
| 1k / 101 | 0.1034 / 0.931 | 0.1034 / 0.931 | 0.000 | 0.000 |
| 1k / 102 | 0.2167 / 0.9167 | 0.2167 / 0.9167 | 0.000 | 0.000 |
| 1k / 103 | 0.250 / 0.875 | 0.250 / 0.875 | 0.000 | 0.000 |
| 10k / 101 | 0.5923 / 0.6758 | 0.5955 / 0.6742 | +0.0032 (worse) | −0.0016 |

Pass requires zombie_rate lower by at least 0.02 **and** correct_version_acc not
lower by more than 0.02 on every public seed 101–103 at 1k and seed 101 at 10k.
No seed meets the zombie bar; at 10k the join is slightly worse, inside the
documented run-to-run spread (v2 10k zombie 0.5907–0.5939 on 2026-11-23).
**T-042 fails again. `subject_join` keeps its `off` default; no measurements or
facts were changed.** This is a synthetic benchmark result: no real-user
accuracy claim is made.

## Borrowed (with ledger ID)

| Component | From | Ledger ID |
|---|---|---|
| Current state over an immutable log; as-of reads | gbrain compiled truth + page versions | T5-03-02, T5-03-22 |
| Idempotency by request key; a different body is rejected | gbrain concurrent-writes | T5-03-20 |
| Greedy token-budget packing | gbrain token-budget.ts | T5-03-17 |
| Deterministic injection gate | gbrain write-gate-patterns | T5-03-13 |
| One central scope filter on every read path | gbrain sourceScopeOpts; mnemonic archive fix | T5-03-21, T5-04-19 |
| Code decides contradictions with an authority ladder | remcycle reconcile | T5-02-03 |
| A negation and number guard on "same statement" | remcycle `_same_statement` | T5-02-04 |
| Correction → demote, nothing deleted | remcycle dreaming | T5-02-10 |
| A session-triggered daily batch | remcycle daily | T5-02-19 |
| "Data, not instructions" framing; single-line items | engram injection marker | T5-01-06 |
| Secret redaction regexes | engram, remcycle, mnemonic | T5-01-18, T5-02-16, T5-04-16 |

## Rejected

| Idea | Source | Why |
|---|---|---|
| Embeddings or vector search in this build | T5-03-15, T5-04-07 | new dependency and latency; the benchmark gave no evidence for it; remcycle chose BM25 first (T5-02-24) |
| An LLM judging recall on the query path | T5-01-03 | 15–20k tokens per moment; breaks the voice budget |
| Hard delete in maintenance | T5-04-12 | breaks as-of, rollback and provenance |
| Demotion on "ignored" alone, or on a cue word alone | T5-01-22, T5-01-24 | harms correct memories: the kill round showed it on Spec-X (`teams/gamma/atk_r1.py` s1) |
| Automatic merge of chains from usage notes ("fusion") | Spec-Z Standout | the kill round showed it hiding a fact nobody ignored (`atk_r1.py` s3) |
| Automatic chain merge from the hybrid score in the review band | this build (F4) | review precision 0.36 at 10k: two of three flagged pairs are different facts |
| A Supabase replica in this build | Spec-Y v2 §j | not measured; out of scope (12) |
