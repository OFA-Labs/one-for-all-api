# E-Brain benchmark harness

Run everything from `benchmark/` with `.venv\Scripts\python.exe` (standard library only, plus pytest).

```
.venv\Scripts\python.exe -m harness.runner --contender control --size 1000 --seed 101 --out results.csv [--timeout-s 900]
.venv\Scripts\python.exe -m harness.generate --size 1000 --seed 101 --out data\ds
.venv\Scripts\python.exe -m pytest -q tests
```

## Modules

| File | Role |
|---|---|
| `generate.py` | Seeded world: ids, codes, subject catalogue, texts, filler |
| `scenarios.py` | Plans the chains and scenarios S1–S11 and H, and lays out the timeline |
| `truth.py` | Sealed ground truth T1–T8 |
| `metrics.py` | The metrics in INTERFACE §4 |
| `loader.py` | Imports `<dir>/adapter.py` and computes the code hash |
| `runner.py` | Drives the flow |

Runner flow:

1. Stream the writes, queries and traces in ts order, with a `maintain()` every 250 writes.
2. Run a final `maintain()`, then the H measurement.
3. Durability probes, then close and reopen.
4. `rollback` checks: rb1 at 60% of the stream, and rb2 at 40% after an extra `maintain()`.
5. Two-instance write check.
6. Score the run and append the rows to the CSV.

Metric definitions follow INTERFACE §4. The interpretation choices are in `../CONTRACT_ISSUES.md`. The extra rows are:
- `zombie_rate_target_chain`: a diagnostic that counts only codes of the queried chain.
- `render_mismatch`, `rendered_extra_codes`: integrity checks on rendered bundles.
- `rejected_malformed_rate`, `rejected_valid_writes`, `store_reopen_ok`, `crashes`, `runtime_s`.

## Known limitations

- The budget is checked between adapter calls, so a single call that never returns cannot be interrupted.
- The physical 2-process S2 test and the S5 kill partway through a batch were descoped. The in-process two-instance check replaces them.
- Some n values are small at 1k (S8: 2, H1: 3, attacks: 6), so read 1k scenario rates with care.
