# one-for-all-api

Backend for ONE FOR ALL.

E-Brain is EXPERIMENTAL shared project memory for Claude Code, Codex and the
voice agent. M1 ports the reference SQLite store and authenticated HTTP API:
accepted writes retain their history, queries select admissible current values,
and every read is scoped to the authenticated user and agent's visibility.

Use Python 3.12 and the exact Builder-Ready reference pins:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -q
```

The M1 suite passes **55 tests, with 1 skipped**. This includes two CORS
regressions and an encoded path-chain history regression beyond the spec's 52
passing tests. The existing CSV comparison skips because benchmark CSVs are not
shipped in this repo. The seven reference test
files remain unchanged; `tests/test_bridges.py` adds the product-spec amendment
check and expects a sibling `one-for-all-web` checkout.

Configure `EBRAIN_TOKENS` outside the repository before using authenticated
routes. It maps bearer tokens to `user`, `agent` and `human` identities; requests
without a recognized token receive HTTP 401. An unset or invalid token map fails
closed. `EBRAIN_DATA_DIR` optionally selects the directory containing
`ebrain.sqlite`; its default is the local application-data directory under
`one-for-all/ebrain`. Never commit real tokens.

Run the service on the local interface only:

```powershell
.venv\Scripts\python.exe -m uvicorn ebrain.api:app --host 127.0.0.1 --port 8765
```

The API exposes `/v1/ebrain/write`, `/v1/ebrain/query` and `/v1/ebrain/limits`,
plus history, human approval/resolution, rollback and delete-my-data routes.
Human authority comes from the token, not a request's claimed identity.
Browser access permits only the local web origins `http://127.0.0.1:3000` and
`http://127.0.0.1:3100`, using bearer headers without cookies. Other origins do
not pass CORS preflight; authentication remains required for API operations.

Every measured capability and limitation is supplied by
`GET /v1/ebrain/limits` from the generated `ebrain/limits_facts.json`; those
measurements use synthetic data, not real-use evidence. Self-heal defaults to
approval required and experimental subject joining defaults to OFF. Above the
tested memory range, bundles carry `beyond_tested_range`. Power-loss durability
and real-agent accuracy remain unmeasured. The web capacity view ships in M1;
the fuller honesty UI, agent hooks, voice client and real-port ablation belong
to later milestones.

Implementation choices and spec discrepancies are recorded in
[the decisions log](docs/ebrain/DECISIONS_LOG.md).
