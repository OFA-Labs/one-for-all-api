# C3 — In-App Navigation and Interaction
**Purpose:** §5 C3 · **Depends on:** 07, 04 · **Files likely touched:** `api/ofa/harness/*`, `api/ofa/harness/adapters/*.yaml` · **Done when:** M05 rows H6–H8 pass.

- Generic method: `screen()` → engine picks element id → helper acts → `screen()` again; verify the expected change (observation hash differs, target text present).
- Actions: click, select, scroll, type, copy/paste (clipboard only for non-secret content), drag (SendInput press-move-release), shortcuts, multi-step navigation.
- Adapters add hints only; absence must not break the flow. Test on ≥ 1 app with no adapter.
- Click/key effects tier-classified by 04 (a "Send" button = Tier 2).
