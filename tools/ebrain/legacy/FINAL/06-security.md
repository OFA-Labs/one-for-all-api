# 06 Security

| Threat | Requirement | Mechanism | Evidence (synthetic benchmark unless stated) |
|---|---|---|---|
| Cross-project or cross-agent read | R-006 | the T8 predicate `(vis='shared' OR agent=?)` and `project`/`user_id` sit inside the SQL before ranking and truncation | leak_count 0 in every measured run (7 sealed + public runs) |
| Private-write status side channel (judge ADR-6) | R-010 | the replay uses only viewer-visible ops, so another agent's private supersession no longer changes what a viewer sees | the reference test T-010; v2 had this channel (`teams/gamma/spec_v1.md` §n.3) |
| External content overwriting first-party values | R-005 | T3 in the replay, plus external+supersedes always routed into the target chain | injection_success_rate 0 in all runs; hijack, poison and spoof classes 0 |
| Instruction payloads or authority claimed in text | R-003 | `GATE_RE` and `SPOOF_RE` flag `injection`/`spoof` and `untrusted`; flagged versions are never current; the rendered text quotes them under "data, not instructions" | as above |
| Cross-user access | R-014, R-015, R-060 | every row has `user_id`; a Store is bound to the token's user; op_id is unique per user | T-015, T-016, T-017, T-060 |
| Misconfigured auth | R-025 | an unset or invalid `EBRAIN_TOKENS` means every request gets 401 (fail closed) | T-025 |
| Agent spoofing another agent or a human | R-060, R-061 | identity comes from the bearer token (`EBRAIN_TOKENS`). `authority="human"` is accepted only from `is_human` tokens. Agent tokens sending `authority="human"` are downgraded to `agent` and logged. | T-061 (passes on the reference API, Python 3.12.10) |
| Secrets stored | R-003, R-092 | `SECRET_RE` redacts before insert; exports and UI only ever read redacted text | the reference test T-003; T-092 for exports |
| Delete my data (SPEC B11.3) | R-091 | `DELETE /v1/ebrain/me` deletes all rows for `user_id` in one transaction, then `VACUUM` | T-091 |
| Concurrent writers | R-011 | `BEGIN IMMEDIATE` per write; ack after COMMIT; WAL | acked_lost 0 in all runs; two-process test T-011 |
| Power loss | none | `synchronous=NORMAL` can lose the last transaction on OS crash or power loss (it survives a process kill). Set `sqlite_synchronous=FULL` to trade write latency for this. | ARGUED (SQLite documentation behaviour); not measured |
| API reachable from the LAN | R-060 | binds `127.0.0.1` only (`api_host`); the website calls it from the same machine | T-060 |

**What is not protected (stated plainly).**
- The gate regexes catch the attack phrasings in the benchmark plus standard families. A novel phrasing that names no supersedes target and starts its own chain can still be shown as `current` with the `UNTRUSTED` flag. That happens only when no first-party value exists for that subject.
- Write text is not encrypted at rest. The database is a plain file in the user's profile.
