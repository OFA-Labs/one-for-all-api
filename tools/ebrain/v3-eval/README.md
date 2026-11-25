# V3 evaluation harness (test-only)

This directory is a **test-only, synthetic, deterministic** evaluation harness
for the proposed E-Brain V3. It is not product code, imports nothing from
`ebrain/`, calls no model, uses no network and reads no secret. It produces no
accuracy claim about V3 because V3 is not implemented here.

The directory name contains a hyphen, so Python cannot import it by that name.
The real source lives **only** in this directory. `tools/ebrain/v3_eval/` is a
thin importable alias: six tiny loaders plus a physical `cli.py` launcher. On
Windows PowerShell, from the API repository root:

```powershell
$env:PYTHONPATH = "C:\Users\jaiva\OneDrive\Desktop\voice-agents\one-for-all-api"
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli --help
```

`python -m` from the repository root also works without setting `PYTHONPATH`,
because the current directory is already on `sys.path`. Direct path
invocation is not supported (the aliased relative imports require the package
context); use `-m` as shown. Verify the alias with:

```powershell
& ./.venv/Scripts/python.exe -c "from tools.ebrain.v3_eval import generator; print(generator.__file__)"
```

## Commands

```powershell
# Frozen protocol, version, seeds, sizes, thresholds, failure policy + hash
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli protocol

# Count + hash without writing anything (fast, works at 100k)
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli generate --seed 101 --size 100000 --mode distinct_fact_count --stream

# Write events.jsonl + sealed dataset_manifest.json
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli generate --seed 101 --size 1000 --mode event_count --out <dir>

# One contender in a clean subprocess; optional --threshold override
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli evaluate --adapter <adapter.py> --seed 101 --size 1000 --mode event_count --evidence-dir <dir>

# All seven intentionally broken contenders must be rejected
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli negative-controls

# Verify a sealed manifest, or a sealed-suite commitment
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli verify-manifest --manifest <dir>/dataset_manifest.json
& ./.venv/Scripts/python.exe -m tools.ebrain.v3_eval.cli verify-manifest --commitment <sha256> --payload <sealed-payload.json>
```

Exit codes: `0` OK, `2` usage, `3` NOT_RUN (adapter missing / zero
denominator), `4` FAIL (threshold or gate breach), `5` negative-control
broken (a control unexpectedly passed), `6` manifest/commitment mismatch,
`7` worker error. A missing adapter is always **NOT_RUN**, never a measured
result. `--help` exists at the top level and for every subcommand.

A contender adapter is a module exposing `class Adapter` with
`__init__(config, workdir)`, `write(event) -> {"status": ...}` and
`query(case) -> answer dict`; `close()` is optional. The runner spawns a fresh
interpreter per contender and imports the adapter under a unique module name,
so a cached module cannot be substituted for the requested contender. Adapter
environment variables whose names look like secrets are removed, and only
whitelisted answer fields are returned. Fixtures under `fixtures/` show a
reference contender, a distinct product-style contender and a true-plus-zombie
negative control.

## Dataset formats

* `events.jsonl` — one public event per line: `seq`, `op_id`, `ts`, `action`
  (`create|revise|erase`), `key`, `scope`, `source`, `authority`, `value`,
  `revision`, `supersedes`, `history`, `facets`, `scenario`. Keys are qualified
  `repo|branch|namespace|environment|T{index:08d}`; the integer token
  guarantees 100k distinct keys without a finite catalogue. `event_count`
  mode emits exactly `size` events over `size / 20` revision chains;
  `distinct_fact_count` mode emits exactly `size` unique keys plus revisions
  of those keys (events and keys are counted separately in the manifest).
  No oracle identifier or ground-truth label is present in this file.
* `dataset_manifest.json` — sealed (`manifest_sha256`) counts, seed, mode,
  protocol hash, `stream_sha256`, hash algorithm version and file digest.
* `fixtures/miniature_history.json` + `expected_miniature.json` — a 10-event,
  hand-reviewed history and oracle output covering sequential, conflict,
  late, future, erased and scoped cases. Hidden labels appear only in the
  oracle-side expected file, never in the public history.

The oracle (`oracle.py`) computes the authorized current set, per-fact state,
receipt decisions, knowledge cuts and hidden labels from its own documented
rules. The primary metric is **JOINT EXACT** (authorized set + state +
provenance + actually delivered facets); legacy presence is reported
separately and cannot compensate. Filing, retrieval per arm, conflict/as-of,
abstention and delivered-after-clipping use explicit per-seed/per-scenario
denominators; empty denominators are `UNMEASURED`/NOT_RUN.

`protocol.json` is frozen. Public seeds 101/102/103 are disclosed; the sealed
suite is `NOT_CONFIGURED`. A sealed payload is committed as
`sha256(canonical_json(payload))`; tuning on a sealed failure retires that
suite permanently (`manifest.retire_suite` / `check_suite`). Cache keys must
be sanitized inputs + scope + full manifest, never labels.

## Tests

```powershell
& ./.venv/Scripts/python.exe -m pytest tests/v3/test_eval_protocol.py tests/v3/test_contracts_v3.py -q
& ./.venv/Scripts/python.exe -m pytest tests -q
```

Schema-3 fixtures live in `docs/ebrain/contracts/v3/`. `schema.py` is a
self-contained strict validator for the keyword subset used by those fixtures
(no `jsonschema` dependency); the schemas are the single source of truth for
the expected enums and required fields exercised by the contract tests.
