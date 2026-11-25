# 02 Data model

**Engine and file.** SQLite 3 (Python stdlib `sqlite3`) runs with `journal_mode=WAL`, `busy_timeout=60000` and `synchronous` = config `sqlite_synchronous` (default `NORMAL`). The file is `<data_dir>/ebrain.sqlite`.

**Tenancy (R-014, R-015).** Every table has `user_id`. Every statement in `store.py` filters on the Store's `user_id`, and every project-level statement also filters on `project`.

**DDL.** The DDL below is exactly `store.SCHEMA`. All INSERTs name their columns.

```sql
CREATE TABLE IF NOT EXISTS ops(seq INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
  op_id TEXT NOT NULL, ts INTEGER, agent TEXT, project TEXT, vis TEXT, kind TEXT, text TEXT,
  path TEXT, auth INTEGER, ext INTEGER, sup TEXT, deleted INTEGER, digest TEXT, chain TEXT,
  role TEXT, code TEXT, flags TEXT, UNIQUE(user_id, op_id));
CREATE INDEX IF NOT EXISTS ops_chain ON ops(user_id, project, chain, ts);
CREATE TABLE IF NOT EXISTS codes(user_id TEXT, project TEXT, code TEXT, op_id TEXT,
  PRIMARY KEY(user_id, project, code));
CREATE TABLE IF NOT EXISTS terms(user_id TEXT, project TEXT, term TEXT, op_id TEXT, chain TEXT,
  ts INTEGER, vis TEXT, agent TEXT);
CREATE INDEX IF NOT EXISTS terms_pt ON terms(user_id, project, term);
CREATE INDEX IF NOT EXISTS terms_chain ON terms(user_id, project, chain);
CREATE TABLE IF NOT EXISTS traces(user_id TEXT, session_id TEXT, ts INTEGER, project TEXT,
  body TEXT, PRIMARY KEY(user_id, session_id));
CREATE TABLE IF NOT EXISTS heal(user_id TEXT, project TEXT, op_id TEXT, ts INTEGER, action TEXT,
  reason TEXT, PRIMARY KEY(user_id, op_id, action));
CREATE TABLE IF NOT EXISTS links(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, project TEXT,
  a TEXT, b TEXT, ts INTEGER, kind TEXT, score REAL);
```

## Column rules

| Column | Rule |
|---|---|
| `ops.op_id` | unique **per user** (`UNIQUE(user_id, op_id)`), so two users may reuse an id (T-015) |
| `ops.role` | `version` (new value code, or a human re-assertion: `authority=human` + `supersedes` + only known codes), `copy` (all codes known), `derived` (summary with a new code; never current), `tomb` (`deleted=1`), `note` (no code) |
| `ops.auth` | 0 agent, 1 verified, 2 human |
| `ops.ext` | 1 when `provenance="external"`; fixed at ingest |
| `ops.flags` | comma list drawn from `untrusted`, `injection` and `spoof` |
| `ops.chain` | `p:<path>` or `c:<op_id>`; assigned once, at write |
| `heal.action` | `propose_demote` (no effect on answers) or `demote` (head hidden from `ts` on) |
| `links.kind` | `possible` (EXPERIMENTAL, no effect), `confirmed` (union chains), `split` (clear); the latest per pair wins |
| every row | carries `ts`. `rollback(to_ts, project)` deletes the Store user's rows with `ts > to_ts` (in one project, or in all of the user's projects when `project` is None) |

## Worked example rows (one per table, column order as in the DDL)

| Table | Row |
|---|---|
| ops | `(41, 'u-jai', 'op-3f2a', 1203, 'codex', 'one-for-all', 'shared', 'claim', 'Changed auth-token TTL to 30 minutes per QA feedback (VC-AAAAA2).', NULL, 0, 0, '["op-2b11"]', 0, '9c1e…(sha256)', 'c:op-2b11', 'version', 'VC-AAAAA2', '')` |
| codes | `('u-jai', 'one-for-all', 'VC-AAAAA2', 'op-3f2a')` |
| terms | `('u-jai', 'one-for-all', 'ttl', 'op-3f2a', 'c:op-2b11', 1203, 'shared', 'codex')` |
| traces | `('u-jai', 'sess-77', 1300, 'one-for-all', '{"agent":"claude","shown":["op-3f2a"],"followed":[],"ignored":["op-3f2a"],"note":"Observed TTL 45 minutes in config (VC-AAAAA9)."}')` |
| heal | `('u-jai', 'one-for-all', 'op-3f2a', 1400, 'propose_demote', 'note carries a different value VC-AAAAA9')` |
| links | `(7, 'u-jai', 'one-for-all', 'c:op-9c01', 'c:op-2b11', 1210, 'possible', 0.512)` |

## Derived at read time (never stored)

| Value | How |
|---|---|
| status of an op | `_evolve` over the viewer-visible ops (≤ horizon) of the chain group (chain plus confirmed links) minus `demote` heals |
| status of a restatement | the status of its code's origin op (lineage, R-012) |
| memory_count | `SELECT COUNT(*) FROM ops WHERE user_id=? AND project=?` |
