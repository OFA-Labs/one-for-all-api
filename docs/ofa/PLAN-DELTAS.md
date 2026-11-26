# PLAN-DELTAS

Deviations from `docs/plan/*`, ≤ 10 lines each, newest last. Mark design questions `NEEDS-OPUS`.

1. **2026-11-26 · Base branch.** M00 picked `origin/staging` (00c7d89, has `voice/` + `ofa_execution/`), not a merge. Work on `feat/ofa-core` (api) and `feat/ofa-dashboard` (web). E-Brain edits stashed (`stash@{0}`).
2. **Single venv.** `.venv-ofa` installs the voice-dev + local-execution-dev sets plus extras directly (no `requirements-ofa.lock` yet).
3. **Port.** OFA core serves on `127.0.0.1:8768` (8767 stays with the legacy voice companion).
4. **New executor, not the old Engine thread.** `ofa/executor.py` reuses hands/primitives and the Gate's idea (one-use, digest + epoch bound) but enforces the §6 tiers with spoken approvals; `ofa_execution.Engine` is untouched (its UI-card approvals stay for its own tests).
5. **Live budget caps are totals**, not per milestone: groq 900, deepgram 600, gradium 300 (`ofa/live_budget.py`).
6. **Benchmark uses synthetic speech** (provider TTS) instead of user recordings, per the user's "no physical checks" instruction. Real-voice accuracy is therefore untested.
7. **Groq dev-tier limit is 8 K tokens/min** (headers). Added compact element lines, post-action glance and short-wait auto-retry on the *same* model (announced aloud; never a model switch). Longer waits still ask.
8. **Fast path (HassIL, zero-LLM) not wired** into the new runtime; every turn goes through the engine (§7.3 default). The legacy companion still has it.
9. **Stage 2.** Backend `OpenAICompatEngine` (Mode B engine plug-in) built; OFA Engine UI and Claude Code/Cursor Mode A not built — standing decision §0.1 + terms (see CAPABILITY_REALITY).
10. **Phone.** Reimplemented a minimal adb surface (no phone-harness code, no install); `helpers.py` at a pinned SHA was not reviewed because nothing was copied.
11. **Web.** New `/ofa` dashboard route + nav item; existing pages untouched. `.next` OneDrive placeholders had to be cleared to build.
