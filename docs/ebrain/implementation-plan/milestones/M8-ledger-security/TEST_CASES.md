# M8 acceptance cases

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C03 | Kill worker immediately after committed write; query exact and text with/without receipt | Authoritative transition/pending, never stale current; resume converges; no lost ack. |
| C04-foundation | Same IDs in two orgs; foreign scope FKs; runtime-role joins/upserts; pooled context reuse | No cross-scope row/identifier/count; FK/RLS fail closed; context cleared. |
| C05-foundation | Server recorded cut with delayed/future client clock | Knowledge order follows commits; valid interval retained; unknown time explicit. |
| C06-foundation | Barrier-sync same key retries and conflicting request digests; concurrent last reservation | One semantic event/key, digest mismatch 409, transactional quota; no partial event/job. |
| C07 | Synthetic secret in nested/encoded/malformed/oversized/compressed inputs; scanner down | Rejected/redacted before DB/object/log/job/model; quarantine bounded and not searchable. |
| LEDGER-FAULT | Timeout after commit, rollback before commit, crash after object staging, duplicate job | Same-key receipt recovery; no false ack; orphan cleanup; idempotent application. |
| FENCE-ELIGIBILITY | External/unauthorized agent mentions higher-authority fact; authorized ambiguous update | First cannot force human current unavailable; latter fences eligible impact until adjudicated. |
| SNAPSHOT-AUTH | Revoke permission during query; min_seq ahead of replica | Retry/deny before delivery; primary or pending, never stale authorized cache. |
| QUOTA-BASE | Concurrent bounded pending/event admissions and exact retries | Counters/reservations atomic; no accepted content silently expires. |

Record restricted database role, schema/policy hash, fault point, committed seqs, acknowledgments and recovered rows. Test missing prerequisites explicitly; do not silently substitute SQLite.
