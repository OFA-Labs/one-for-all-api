# C1 — Session and Presence
**Purpose:** §5 C1 design · **Depends on:** 02, 03, 04 · **Files likely touched:** `api/voice/{hotkey,overlay,session}.py`, `api/ofa/session.py` · **Done when:** M01 rows S1–S9 pass.

- State machine `ofa/session.py`: `OFF → ACTIVE{idle, listening, thinking, acting, speaking, awaiting_approval, error}`; `epoch` increments on every start/stop.
- Caps Lock: low-level keyboard hook (existing `hotkey.py`) **swallows** the key (no toggle) so capitalization never changes; test asserts `GetKeyState(VK_CAPITAL)` unchanged. Shift+Caps passes through as real Caps Lock (escape hatch).
- Second press = end + kill switch (04 §Kill switch). Silence or task completion never ends the session.
- Orb: `overlay.py` topmost, click-through, top-center, 7 distinct states; "mic live" ring whenever audio streams to cloud (§8.7).
- Completion phrase only after `verify.ok`: "Completed. Anything else?" / Hindi pref: "Ho gaya. Aur kuch?"; partial/failure → specific spoken report.
- Preferred name from profile D0 (`memory.profile.preferred_name`).
- Voice controls handled before the engine by a deterministic matcher: stop / cancel / ruko / pause / resume; correction ("nahi, matlab…", "no, I meant…") → forwarded to engine as revision.
