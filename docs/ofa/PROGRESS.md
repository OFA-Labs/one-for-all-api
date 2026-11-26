# PROGRESS

Honest detail: `docs/CAPABILITY_REALITY.md`. Deviations: `docs/PLAN-DELTAS.md`.

| Milestone | Status | Evidence / note |
|---|---|---|
| P (plan) | ✅ 2026-11-26 | `docs/plan/*` |
| M00 baseline | ✅ | branch `feat/ofa-core` from `origin/staging`; E-Brain edits in `stash@{0}`; `.venv-ofa`; keys found (Groq via KRY fallback, speech keys in DPAPI) |
| M01 voice loop/orb/kill switch | ✅ built · ⚠ no human mic run | `ofa/speech/loop.py`, `ofa/orb.py`; `test_runtime.py` |
| M02 approval/vault/broker/audit/canaries | ✅ | `ofa/policy`, `ofa/vault`, `ofa/egress.py`, `ofa/audit.py`; tests |
| M03 engine + orchestrator | ✅ live | `ofa/engine`, `ofa/orchestrator.py`; live Groq turns |
| M04 voice routing + benchmark | ✅ synthetic | `docs/ofa/bench/results-2026-11-26.md`; routing in `ofa/runtime.py` |
| M05 harness C2/C3 | ✅ Win32 · ⚠ Electron weak | `ofa/harness`; `test_windows_real.py` 5/5 |
| M06 dictation | ✅ | verbatim enforced in executor; `test_text.py`, orchestrator tests |
| M07 search + references | ◐ partial | loop/near-match/resolve built; no pagination engine |
| M08 sign-in/forms/files + vault UI | ◐ built, real sites untested | `ofa/ui/vault.html`, mock pages, dry-run |
| M09 plans + workflows | ◐ built, no real destinations | plan gate, ledger, no-duplicate |
| M10 phone (optional) | ◐ built, no device | `ofa/phone.py` (adb missing) |
| M11 hardening + generalization | ✅ run | `docs/ofa/bench/generalization-2026-11-26.md` |
| M12 Stage 2 | ◐ backend plug-in only | `OpenAICompatEngine`; UI/Mode A not built |
| Web dashboard | ✅ | `one-for-all-web@feat/ofa-dashboard` `/ofa`, Playwright 4/4 |

Tests: API `tests/ofa` 228 passed (fakes) + 5 real-desktop; web typecheck/lint/arch/build ok.
Live calls used: see `docs/ofa/bench/live-calls.json` (caps in `ofa/live_budget.py`).

**Next action (needs you):** real-voice trial with headphones (`python -m ofa`), test accounts for the minimum surfaces, consider a paid Groq plan.
