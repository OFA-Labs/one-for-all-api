# C5 — Goal-Driven Search and Browsing
**Purpose:** §5 C5, §3.3 · **Depends on:** 06, 07 · **Files likely touched:** `api/ofa/goal_loop.py`, `api/ofa/memory.py` · **Done when:** M07 rows G1–G6 pass.

- Engine converts the request to `Goal{criteria[], source, stop_conditions, max_iterations=50}`; criteria come only from what the user stated.
- Loop: observe → extract candidates → check every criterion (engine judgement with evidence quote; deterministic checks for numbers/dates/locations) → next page/scroll.
- Stop: met | user interrupt | exhausted (no new candidates for 2 iterations) | blocked | loop (same observation hash ×3) → spoken reason.
- Near match reported as "closest, but it fails <criterion>", never as a match.
- Results stored in `memory.context.last_results` for "that one / the second one / usko bhejo".
- Reference resolution (§3.3): `memory.resolve(ref)` over last results, last file, current app, contacts/roles from profile; > 1 plausible → spoken question.
