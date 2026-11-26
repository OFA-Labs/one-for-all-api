# C10 — Plan → Approve → Execute
**Purpose:** §5 C10 · **Depends on:** 06, 04 · **Files likely touched:** `api/ofa/planner.py` · **Done when:** M09 rows P1–P6 pass.

- Complexity check (deterministic + engine hint): ≥ 3 dependent steps, ≥ 2 apps, Tier 2 step needing reasoning, or engine flags it.
- Say "Let me build a plan." → engine `plan(steps[])` (step, app, effect tier, destination) → spoken numbered plan (≤ 7 items; longer shown on screen + summary).
- Plan approval via lexicon (04) binds the plan digest; edits → re-plan → re-ask.
- Execution: progress line per step or every 10 s; material change (new destination, new Tier 2 step, scope) → pause + re-approve.
- Plan approval never replaces per-action Tier 2 approval.
