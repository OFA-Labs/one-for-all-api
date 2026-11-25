# Migration and recovery implementation runbook

This runbook is to implement and rehearse in M13/M14; no real service/data migration was performed during planning. D05/D11 and concrete cutover approval gate production. The legacy `Store.rollback` deletes rows and must not be used for migration rollback.

## 1. Inventory and immutable export

Inspect actual SQLite SCHEMA/TABLES and data ownership in a separately authorized snapshot: current code includes ops/codes/terms/traces/heal/links with user/project semantics. Record row counts, schema/source hashes, source namespace, last accepted operations and backup verification. Never infer org/team from an arbitrary project string or default all rows to organization-wide. Map owner-approved user/project/visibility to org/scope/grants explicitly; ambiguous ownership quarantined.

Use a consistent SQLite backup/export with an agreed high-water mark. Archive encrypted and restricted; copy sanitized fixture first for rehearsal. Secrets/PII gate applies before new durable stores; import is not an exception. Preserve original provenance and every accepted event or a documented reviewed quarantine/rejection reason. Source evidence may be absent in legacy plain text: do not fabricate source spans or assert approved truth.

## 2. Deterministic transformation

Namespace `(source_instance, legacy_user, legacy_op_id)` into new org/op/claim IDs using a documented deterministic map. Preserve legacy codes as scoped aliases, original ts as client/legacy metadata, unknown effective time as unknown and import knowledge cut as new server sequence. Do not invent effective timestamps from file modification time. Classify decisions/observations/derived/external under approved policy; legacy authority integer or human-looking text is not a new grant.

Treat fuzzy chain IDs as candidate grouping, not verified identity. Reconstruct exact scoped keys/lineage from approved evidence; mixed chains and ambiguous qualifiers pending with fences. Preserve approved legacy human actions as attributable evidence only after authority mapping review. Tombstones, source retraction and legacy physical deletions have different semantics; document irrecoverable missing events, never claim reconstructed history.

## 3. Capture concurrent changes

Choose proven transactional change log/CDC or planned short write freeze + final export; prefer freeze if no reliable CDC. Record immutable source snapshot and last captured mark. Replay deltas idempotently; digest/count/receipt compare per scope. One authoritative writer at all times; diagnostic mirror is not uncoordinated dual-write. No query-side migration writes.

## 4. Shadow and reconcile

Build cards/search at named cut, verify approved identity/state, source/citation coverage, pending/conflict/quarantine and quota reservations. Reconcile all accepted legacy events to exactly one mapped event or explicit reviewed disposition, zero unexplained lost/duplicate. Compare old/new on compatible scenarios plus expected approved differences (e.g. lower authority can no longer override by supersedes). New pending/conflict never falls back to old current. Restricted security tests cover references, errors/counts, historical access and suppressed payloads. Publish reconciliation manifest and independently reviewed mapping samples.

## 5. Cutover rehearsal and production gate

In isolated rehearsal: drain source, freeze writer, final delta, verify counts/digests/mark, activate one new writer, run client contract/current/canary checks and accept new synthetic events. Rehearse interruption at each step. Demonstrate rollback with those new events, current grants and erasure markers preserved. Prepare concrete maintenance window, backup location/checksum, completed restore result, latest suppression proof, operator/abort criteria and recovery path for owner approval; approval is the final step before production action.

On authorized production cutover: acquire writer fence, drain source/final delta, verify manifest/current grants, activate new writer and scoped clients, monitor stale-current/leak/injection/accepted-loss/error/lag/quota/review canaries. Any integrity/security violation stops affected serving; queue pressure never auto-approves review. Record exact activation sequence and operator.

## 6. Rollback and disaster recovery

Feature/model/index rollback uses compatible pointers and current authoritative ledger cut, auth and suppression. Reversing writer cutover requires a tested reverse transformation for **all** post-cutover events/identity/decision/grant/erasure semantics; if unavailable, freeze writes and repair forward. Do not point clients at the stale SQLite snapshot. Keep accepted event exports and durable receipts for reconciliation.

Disaster restore is isolated and initially read-closed: restore consistent DB/WAL/object/manifest, apply independently recovered latest suppression/revocations, replay to approved target, reconcile counts/digests/quotas, rebuild projections, verify RLS/security/erased absence and fence old writer. Unknown latest suppression => remain closed. Measure actual RPO/RTO; configured backup interval is not a measured RPO. Lost acknowledged disaster events, even within RPO, are reported incidents. Historical/logical rollback cannot resurrect erased content.

## 7. Decommission

Keep old DB restricted/encrypted read-only for approved rollback/retention window, with no independent active writer. Decommission only after reconciliation/pilot/recovery acceptance; deletion itself needs the policy-authorized disposition. Final report includes source/new manifests, mapping/quarantine table, lost/duplicate counts, independent tests, cutover/recovery proof, residual gaps and operational owner. Cleanup of the obsolete source folders in this planning task does not delete any owner application-data database.
