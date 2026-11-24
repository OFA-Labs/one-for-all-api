# one-for-all-api

Backend for ONE FOR ALL.

E-Brain is EXPERIMENTAL shared project memory for Claude Code, Codex and the
voice agent. This branch is the **M0 scaffold**: the store intentionally raises
`NotImplementedError("M1")`. Memory storage and retrieval are not implemented
in this milestone.

Use Python 3.12 and the exact Builder-Ready reference pins:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\python.exe -m pytest tests -q
```

M0 is complete only when pytest collects 52 tests and reports **22 failed,
6 passed, 1 skipped, 23 errors** (exit code 1). The store failures are deliberate;
the CSV comparison skips because benchmark CSVs are not shipped in this repo.
The reference tests remain unchanged. M1 replaces the stub with the real store.

Implementation choices and spec discrepancies are recorded in
[the decisions log](docs/ebrain/DECISIONS_LOG.md).
