# 00 — Plan Index
**Purpose:** entry point for the Implementer · **Depends on:** `docs/MASTER_PROMPT.md` (cited as §n) · **Files likely touched:** none · **Done when:** every milestone in the table is green or deferred.

Path aliases used everywhere: `api/` = `one-for-all-api/`, `web/` = `one-for-all-web/`. Plan written 2026-11-26 (Session P).
Do not enter `.worktrees/`; use git refs only. Follow `COMMIT_POLICY.md` (root). Attribution per user memory.

## File map
| File | One line |
|---|---|
| 01-current-state.md | What exists in api/web; keep / modify / replace |
| 02-architecture.md | Components, data flow, package layout, run commands, latency targets |
| 03-voice.md | Provider facts, routing, benchmark plan, Hindi/Hinglish, echo |
| 04-approval-and-security.md | Approval engine, yes-lexicon, threat model, audit log |
| 05-vault-and-broker.md | Handles, vault crypto, broker flow, egress guard, canaries, enrollment |
| 06-engine.md | `ReasoningEngine` interface, Groq adapter, model choice, Stage 2 |
| 07-desktop-and-phone.md | Desktop harness on Windows; Phone Harness decision + evidence |
| caps/C1..C10 | Per-capability design notes (short) |
| 08-tests.md | Test strategy + traceability matrix |
| 09-risks-and-needs.md | Risks, unknowns, what the user must provide |

## Milestone order
| # | File | Summary | Depends |
|---|---|---|---|
| M00 | milestones/M00.md | Checkpoint, branch, env loader (KRY fallback), key probes, run existing apps | — |
| M01 | milestones/M01.md | Unified runtime: persistent Caps session, 7 orb states, kill switch, echo guard, both providers | M00 |
| M02 | milestones/M02.md | Approval engine, audit log, egress guard + canaries, vault, broker (tests first) | M00 |
| M03 | milestones/M03.md | `ReasoningEngine` + Groq adapter, model comparison, orchestrator loop | M01, M02 |
| M04 | milestones/M04.md | Voice routing + fixed benchmark EN/HI/Hinglish, Hindi numerals, transliteration | M01 |
| M05 | milestones/M05.md | Desktop harness (UIA → OCR → vision) + C2/C3 | M03 |
| M06 | milestones/M06.md | Dictation verbatim/compose (C4) | M04, M05 |
| M07 | milestones/M07.md | Goal-driven search + context/reference store (C5, §3.3) | M05 |
| M08 | milestones/M08.md | Sign-in, forms, files (C6–C8), enrollment UI, dry-run fill | M02, M05 |
| M09 | milestones/M09.md | Plan→approve→execute, multi-app workflows (C9–C10) | M07, M08 |
| M10 | milestones/M10.md | OPTIONAL Android phone surface (adb) | M05 |
| M11 | milestones/M11.md | Hardening, generalization tests, final report (§14) | all |
| M12 | milestones/M12.md | Stage 2 DEFERRED: Mode A1/A2 + OFA Engine UI | M11 |

Order change vs §12.1: none. M02 before M03 so no LLM-driven effect ever exists without the approval engine.

## Live-call budget (hard caps; tests marked `@pytest.mark.live`, opt-in via `OFA_LIVE=1`)
| Milestone | Groq | Deepgram | Gradium | Notes |
|---|---|---|---|---|
| M00 | 1 | 1 | 1 | one probe each (Groq already probed in P: 1 call) |
| M01 | 0 | 10 | 10 | smoke of STT/TTS each |
| M02 | 0 | 0 | 0 | fakes only |
| M03 | 60 | 0 | 0 | 3 models × 15 prompts + 15 spare |
| M04 | 0 | 180 | 90 | 60 utt × (Flux, Nova-3) + 60 EN on Gradium + 30 TTS samples each |
| M05–M09 | 80 each | 20 each | 10 each | end-to-end slices |
| M10 | 20 | 0 | 0 | optional |
| M11 | 200 | 100 | 50 | generalization (§13) |
A counter `api/ofa/live_budget.py` (M00) persists counts in `docs/ofa/bench/live-calls.json`; a test exceeding its cap fails.

## Traceability
Matrix: `08-tests.md` §Matrix. Progress: `docs/PROGRESS.md`. Deviations: `docs/PLAN-DELTAS.md`.
