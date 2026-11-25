# 05 Event flows

## 1. Write

```
Agent ──POST /v1/ebrain/write (Bearer)──> api.py ──auth: token → (user, agent)──> Store.write
Store.write: validate → BEGIN IMMEDIATE → idempotency (digest) → gate (redact, flags)
           → roles via codes table → _assign_chain → INSERT ops, codes, terms, [links possible]
           → COMMIT → WriteAck(accepted=True)          # ack only after COMMIT (R-011)
```

## 2. Concurrent conflicting writes (Claude and Codex, same ts)

```
claude: write(c1, ts=5, "OTP length is 4 (VC-…1)")   codex: write(c2, ts=5, "OTP length is 8 (VC-…2)")
  both BEGIN IMMEDIATE → SQLite serialises them; both commit; both acked; nothing rejected
query(ts ≥ 5): replay sees two same-ts candidates, two agents, one base → T4
  → items c1 and c2 status conflicted + flag conflict; no current item
human (UI Inbox) → POST /v1/ebrain/resolve {pick c2} → authority=human op superseding {c1, c2}
  → the next query shows c2's value as current (T1 + T2)
```

Measured (synthetic sealed seeds): conflict_acc 0.50–1.00 at 1k and 0.47–0.68 at 10k. The UI therefore labels this capability "can't reliably".

## 3. Retrieval

```
Agent ──POST /v1/ebrain/query──> Store.query: BEGIN (read snapshot)
  → _rank (T8 in SQL) → per chain group _chain_ops(viewer) → _evolve → demotions → items
  → capacity check → _render(budget) → COMMIT → Bundle + capacity_state
```

## 4. Self-heal (default `propose`)

```
Agent session ends ──POST /v1/ebrain/observe (trace)
maintain trigger: Claude Code Stop hook runs `python -m ebrain maintain` (POST /v1/ebrain/maintain)
  → Store.maintain(now): propose_demote rows (no effect on answers)
UI Heal tab → GET /v1/ebrain/heal → human clicks Approve → POST /v1/ebrain/heal/{op}/approve
  → heal(demote, ts) → the head is hidden from ts on
Undo: POST /v1/ebrain/rollback {to_ts: approval ts − 1}
```

## 5. Rollback

```
human → POST /v1/ebrain/rollback {to_ts: t, project_id: "one-for-all" | null}
  → api: Store(data_dir, cfg, token.user) → Store.rollback(t, project)
  → BEGIN IMMEDIATE → DELETE codes of this user's (project's) ops with ts>t
  → DELETE FROM terms, ops, heal, traces, links WHERE user_id=? [AND project=?] AND ts > t → COMMIT
  → other users' rows are untouched (T-016)
  → queries at horizon t return exactly what they returned at t (rollback_exact = 1 on every measured run)
```

Rollback is destructive for writes after t. The UI MUST ask for confirmation and show the count of rows to be removed.

## 6. possible_same_fact (only when `subject_join = on`)

```
write w (unjoined by the v2 rule) → hybrid score h vs best chain c
  h ≥ 0.70 and no clash → join c
  0.45 ≤ h < 0.70 → new chain + links(possible) → both chains' items carry possible_same_fact
UI Pairs tab → Confirm → links(confirmed) → the replay unions both chains (later write current)
            → Split  → links(split) → flag cleared
```
