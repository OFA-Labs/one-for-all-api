# M11 acceptance cases

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C01 | Agent forges human role/approval and references human head; valid bounded delegate then writes | Forgery never changes current or creates denial-conflict; delegate succeeds only within granted predicate/scope/time. |
| C05 | Late observation, future decision, retro-correction, equal server times, old identity/policy cut | Correct valid/knowledge semantics, scheduled state, no backdated knowledge; current auth on every cut. |
| C06 | Barrier-synchronized competing writes with shared base, unequal clocks; known stale-base request | First cut valid; second eligible branch conflict/no current; stale attempt rejected/noncurrent. |
| C09 | Edit target after proposal; revoke reviewer; duplicate/concurrent approval; cross-scope promotion | Exact digest/CAS/permission enforced; no stale, self or double action. |
| C10-logical | Tombstone then old-state rollback; legitimate restore; erased target; multi-fact failure | No implicit resurrection/erased bytes; explicit new decision; full history; no hidden partial batch. |
| H09 | Intended TTL 30m, observed prod 60m, expired source, source revision retracted | Separate intended/observed answers; stale observation unknown; decision validity follows contract. |
| M03 | Missing steward, overdue critical proposal, duplicates | Authorized escalation/dedup/cap; stays pending without auto-approval. |
| M08 | Before/after approved policy activation; unsafe production config toggle | Correct historical replay; unsafe toggle refused; manifest activation audit. |
| RES-PROPERTY | Same admitted ledger under worker batches/rebuild, unrelated fact insertion, equivalent units | Canonical exact result unchanged; one scalar current; independent replay agrees. |

Explicitly retain evidence showing low authority cannot gain permission from lineage, unlike the legacy benchmark’s T2 rule. A successful old benchmark is not approval for that V3 behavior.
