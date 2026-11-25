# E-Brain engineering and evaluation tools

Product runtime lives in `ebrain/`, not here. [The implementation plan](../../docs/ebrain/implementation-plan/README.md) is the next coding agent’s starting point.

`legacy/` is the byte-preserved research subset relocated from the removed top-level `ebrain-tournament/`: frozen FINAL spec/reference/variants/results, original benchmark/harness/fixtures, experiment code/CSVs and judge evidence. Original paths inside those frozen files are historical. Relative FINAL/benchmark/results layout is retained so Python probes and prototype imports continue to work. The original shell drivers may contain absolute workspace/venv paths; use the active wrappers below.

- `scripts/Test-CurrentBackend.ps1`: current backend suite with exact measured-facts sources configured, no environment-file reading.
- `scripts/Invoke-LegacyBenchmark.ps1`: frozen reference/current product contender in a separate interpreter, new CSV and full source/runtime manifest; never overwrites historical measurements.
- `scripts/validate_plan.py`: plan-link, 30-finding traceability and retained-file checksum verification.
- `product-adapter/adapter.py`: test-only glue that imports the actual API Store. Product code must never import frozen reference/prototypes/harness.

No venv/database/cache is copied into this tree. Use the API interpreter for local checks, or create an isolated Python 3.11 environment for original-runtime reproduction. The original harness is deterministic/std-library on the contender path; model-permitting V3 evaluation will be a separate versioned tool created in M7. Do not silently modify frozen INTERFACE.md or its scoring contract.

For archived third-party research clones, rounds/teams/orchestration and the retired offline app, see the verified external recovery archive in [CLEANUP.md](../../docs/ebrain/implementation-plan/CLEANUP.md). Frozen files are evidence, not active repository instructions. `legacy/results/_probe_tmp` was disposable benchmark SQLite state and is omitted.
