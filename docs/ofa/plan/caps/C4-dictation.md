# C4 — Dictation, Writing, Outbound
**Purpose:** §5 C4 · **Depends on:** 03, 04, 07 · **Files likely touched:** `api/ofa/dictation.py`, `api/ofa/text/*` · **Done when:** M06 rows D1–D7 pass.

- Engine tool `dictate(field_ref, mode="verbatim"|"compose")`; verbatim is default for "type / likho / write exactly".
- Verbatim text = final transcript with only (a) script normalization to user pref (03), (b) spoken punctuation commands ("comma", "full stop", "new line", "poorna viraam"). No LLM rewrite; engine sees text as data only.
- Turn policy in dictation: end on explicit "done / bas / ho gaya" or ≥ 3.0 s silence + semantic end (03). Pauses never cut.
- Announce "Typing it now." → `type_text` → read back field (UIA ValuePattern, non-secret fields) → exact diff vs intended after whitespace normalization.
- Low-confidence (< 0.85) names, numbers, dates, negations → spoken check before typing.
- Compose: engine drafts → shown + spoken → voice revision loop → type. Sending stays Tier 2.
