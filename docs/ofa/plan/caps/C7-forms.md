# C7 — Personal Data and Form Filling
**Purpose:** §5 C7 · **Depends on:** 05 · **Files likely touched:** `api/ofa/forms.py` · **Done when:** M08 rows F1–F7 pass.

- Field map: engine receives field labels/types/options + vault **labels** and returns `{field_ref → handle | user_literal | ASK}`.
- Missing value → ask; offer to save (D2 values only via the loopback vault UI, never by voice).
- D2: ask each time before fill. Never invent facts, answers or declarations; consent/declaration boxes always ASK.
- Multi-page/conditional: re-`screen()` after each page; validation errors read back and fixed or asked.
- Before submit: show the filled form on screen, speak summary (labels + D0/D1 values; D2 masked), Tier 2 submit.
