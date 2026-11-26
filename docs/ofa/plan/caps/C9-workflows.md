# C9 — Multi-App Workflows
**Purpose:** §5 C9 · **Depends on:** C10, 04 · **Files likely touched:** `api/ofa/workflow.py` · **Done when:** M09 rows W1–W6 pass.

- Workflow = ordered steps with typed artifacts (`text`, `file`, `table`) passed by reference (hashed artifact store in a temp dir).
- Each destination tracked: `{dest, account, status: pending|sent|failed|unknown}`; idempotency key per (workflow, dest).
- Retry only `failed`; `unknown` → inspect target state (sent folder, channel history) first, else ask (§9).
- Deliverables: md/docx/pdf; a "simple language" flag is passed to the engine.
- Code/repo: read-only by default; untrusted code only in Windows Sandbox (if enabled) else refused; comment/approve/push/merge = Tier 2.
- Final spoken + on-screen report lists every destination status.
