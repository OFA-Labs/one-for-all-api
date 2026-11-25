# Evidence collected by the planning task

The planning task executes existing checks and validates cleanup; it does not implement or benchmark V3. `current-checks.json` contains the final observed check ledger. `git-before.json` captures initial dirty status/hashes; `owner-files-preserved.json` verifies retained owner work after changes. `relocation-manifest.json` records every retained file SHA-256 plus archive/spec hashes. `cleanup-result.json` records removed/preserved paths. Logs are synthetic local test output.

Before cleanup: backend **71 passed, 1 skipped, 1 existing warning**, 27.14s; web typecheck/architecture/lint/build passed, 33 selected browser tests passed in 39.1s. The exact measured-facts test was initially skipped because its CSV paths were unconfigured. Post-cleanup backend run explicitly supplies retained CSVs; its actual result is recorded separately, not inferred. Frozen harness tests and reference/product reproduction are also recorded only after execution.

After cleanup: backend **72 passed, no skips**, 29.12s; frozen harness **12 passed**, 0.55s. Separate reference/product 1k/101 runs reproduced .9310 presence accuracy/.1207 zombie, with zero recorded leak/injection/budget/crash/ack-loss counts. Runtime is API Python 3.12, explicitly recorded in each run manifest. These smoke runs validate the relocation and adapter, not V3 targets.

The reference/prototype 50k CSVs and old public 1k/10k matrices are retained historical measurements, not rerun by the planning task. No new sealed, live model, 50k/100k, Postgres, company security/load/restore, owner-app or real-user accuracy evidence exists here. A successful plan link/hash audit proves document/relocation integrity, not product correctness.
