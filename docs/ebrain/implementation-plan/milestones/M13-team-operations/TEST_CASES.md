# M13 acceptance cases

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C04 | Full two-org/hidden-project reuse, revoked session, ANN/graph/cache/cursor/receipt/export/backup path | Zero unauthorized content/ID/existence disclosures; final grant epoch check; runtime-role proof. |
| C07-erase | Synthetic secret discovered post-admission; erase and restore older backup | Immediate suppression, verified removal across controlled stores; latest suppression before any serving. |
| C10-recovery | Old backup contains revoked grants/erased source; missing suppression authority | No restored access/content; fail closed if latest authority unverified; accepted events reconciled. |
| H08 | Indirect Unicode/encoded injection in repo/tool/model content, forged metadata/MCP request | No unauthorized write/tool/network/disclosure; typed output and original principal scope enforced. |
| H10-ops | DB failover, queue storm, disk full, auth/scanner outage, model down | Explicit backpressure/failure contract; no false ack/stale current; security failures closed. |
| M02 | Inject lag, leak canary, review overdue and failed backup | Safe diagnosis/alert/runbook ownership; no raw content/token telemetry. |
| M03-team | Steward deprovision, self-approved promotion, missing second reviewer | Reassign/escalate/block, never auto-approve. |
| M04 | 200 sessions, separately concurrent request saturation, 100k facts with hot revisions | Declared hardware/workload and correctness/recall/tail/resource results, honest limits. |
| M09 | Truncated transport/no ack, forged use feedback, revoked receipt viewer | Generated/sent/ack/reported separated; unknown preserved; unauthorized feedback/read refused. |
| CLIENT-VOICE | Overlapping queries/scopes, delayed refresh, revoke and expired pack | Older worker cannot overwrite newer valid scope; stale/unverified memory not asserted current; voice nonblocking. |
| CLIENT-AGENT | Real authorized Claude/Codex sessions and Stop fallback/flush sequence | Actual load/capture evidence, idempotency/scope and privacy; delivery not proof of use. |

Security test output must be sanitized; only synthetic secrets can be fixtures. A reported zero count is scoped to the executed threat suite, never a proof of zero production risk.
