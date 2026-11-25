# M7 acceptance cases

All are planned; none is claimed executed by the planning task. Use synthetic data and keep labels outside implementation inputs.

| ID | Setup / stimulus | Must observe |
| --- | --- | --- |
| H05 | Return true current plus one superseded current; then empty for every query | Joint exact fails both answerable cases; zombie detected; no accuracy from empty response. |
| M01 | Schema-1 client, schema-3 client, unknown schema, timed-out committed retry | Compatibility explicit; same idempotency receipt; unknown schema rejected; errors machine readable. |
| M04-generator | Generate 100k events and separately 100k distinct keys with varied revisions | Manifest counts match actual unique qualified keys/events; repeated seed hash stable; no exhaustion. |
| EV-ORACLE | Reviewed sequential, conflict, late, future, erased and scoped histories | Oracle expected states/cuts validated without product imports. |
| EV-LABELS | Scan model/index/request fixtures, caches and adapter inputs | Hidden oracle identifiers/ground-truth codes absent except declared legitimate selectors. |
| EV-SEALED | Simulate sealed reveal followed by tuning | Manifest retired; new independent suite required before release evidence accepted. |
| EV-DENOM | Pending/unassigned write, partial multi-fact query, clipped conflict | Filing miss/pending counted; incomplete answer fails complete gate; delivered metrics match bytes. |
| EV-RUNTIME | Reference and product contender in separate clean subprocesses | Expected module file paths + combined adapter/product digests recorded; no cached reference import. |

Checkpoint record template: ID, source digest, test node IDs, command/cwd, fixture/protocol hash, run manifest, PASS/FAIL/NOT_RUN, failure notes, reviewer.
