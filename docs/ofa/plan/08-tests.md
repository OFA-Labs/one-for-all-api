# 08 — Tests and Traceability
**Purpose:** strategy + requirement→component→milestone→test map · **Depends on:** all specs · **Files likely touched:** `api/tests/ofa/**` · **Done when:** every row is green, deferred, or BLOCKED with evidence.

## Strategy
- `pytest tests/ofa -q -x -m "not live"`: fakes for Groq (`engine/fake.py`, scripted events), Deepgram/Gradium (`voice/fakes.py`, recorded transcripts), OS (`harness/fake.py` with a synthetic element tree). Run time target < 60 s.
- `-m live` only with `OFA_LIVE=1`; every live test calls `live_budget.spend(provider, n)` and fails when it exceeds the 00-INDEX cap.
- `-m windows`: real UIA/OCR against the disposable OFA Test Pad (`ofa_execution/testpad.py`) and the local mock pages (05). Never against personal apps unless a row says "user-run".
- Tests are written first for policy, vault and broker (M02).
- Outputs: tails or failure greps only (§11).

## Matrix
| ID | Requirement (§) | Component | M | Test (file::name or procedure) |
|---|---|---|---|---|
| S1 | Caps starts/ends session (C1) | session, hotkey | M01 | test_session::caps_toggle |
| S2 | Caps state unchanged (C1) | hotkey | M01 | test_hotkey::capital_not_toggled (windows) |
| S3 | Survives many turns; silence doesn't end (C1) | session | M01 | test_session::multi_turn_and_silence |
| S4 | 7 orb states (C1) | overlay | M01 | test_overlay::all_states |
| S5 | Kill switch invalidates approvals (C1, §6) | session, approval | M01/M02 | test_approval::epoch_invalidates |
| S6 | "Completed. Anything else?" only after verify (C1, §9) | orchestrator, verify | M03 | test_orch::no_completion_without_verify |
| S7 | stop/cancel/pause/resume/correction (C1) | session | M01 | test_controls::voice_controls |
| S8 | Preferred name (C1) | memory | M03 | test_orch::preferred_name |
| S9 | Mic only during active session + indicator (§8.7) | audio, overlay | M01 | test_session::no_stream_when_off |
| B1 | Both providers integrated STT+TTS (§4.2) | voice router | M01 | live: test_live_providers (cap M01) |
| B2 | Routing by capability+language (§4.2) | voice_router | M04 | test_router::routes_table |
| B3 | Fallback only where supported, else degraded notice (§4.2) | failover | M04 | test_router::degraded_hindi_tts |
| B4 | Benchmark EN/HI/Hinglish ~20 each (§4.2, §13) | scripts/bench_* | M04 | docs/ofa/bench/results-*.md exists, user-run |
| B5 | Hindi numbers/dates/times (§4.2) | text/hi_numbers | M04 | test_hi_numbers (60 cases) |
| B6 | Transliteration keeps words (§4.2) | text/translit | M04 | test_translit::roundtrip_tokens |
| B7 | Echo/own-voice never a command (§4.2) | echo guard | M01 | test_echo::tts_text_dropped, ::media_yes_ignored |
| B8 | Barge-in, end-of-turn, dictation pauses (§4.2) | session, router | M01/M06 | test_turns::barge_in_stops_tts, ::dictation_pause_kept |
| B9 | Speech-to-speech loop (§4.2) | runtime | M03 | user-run demo + test_e2e_fake::conversation |
| A1 | Tier table incl. unknown→2 (§6) | policy/tiers | M02 | test_tiers::table_cases |
| A2 | Engine cannot lower tier (§6) | tiers | M02 | test_tiers::engine_cannot_lower |
| A3 | Click on "Send"/Enter in compose = Tier 2 (§6) | tiers | M02 | test_tiers::effect_lexicon |
| A4 | Spoken request states action/payload/dest/account (§6) | approval | M02 | test_approval::spoken_template |
| A5 | Echoed "yes" from OFA TTS rejected (§6) | approval, echo | M02 | test_approval::echo_yes |
| A6 | Replay: token single-use (§6) | Gate | M02 | test_approval::reuse_refused |
| A7 | Silence/unclear/"yes but" ≠ approval (§6) | lexicon | M02 | test_lexicon::cases (EN/HI/Hinglish) |
| A8 | Changed payload after approval refused (§6) | Gate | M02 | test_approval::payload_change |
| A9 | Injected "user approved" text has no effect (§6, §8.7) | approval | M02 | test_injection::web_text_approval |
| A10 | Kill switch mid-approval (C1) | session | M02 | test_approval::caps_during_pending |
| A11 | Multi-destination only if all stated (§6) | approval | M02 | test_approval::multi_dest |
| A12 | Expired request refused (§6) | approval | M02 | test_approval::ttl |
| A13 | Audit log redacted + hash-chained (§8.7) | audit | M02 | test_audit::chain_and_redaction |
| A14 | Approval independent of engine/voice/harness (§6) | policy | M02 | test_no_bypass::imports |
| V1–V12 | §8 vault/broker/egress (see 05) | vault, broker, egress | M02/M08 | test_vault, test_broker, test_egress |
| Q1 | Local services loopback-only + auth token; per-user data (§8.7) | server, runtime | M01/M08 | test_server::loopback_and_token |
| Q2 | User can view/revoke/delete stored data, audit, memory (§8.7, §3.3) | audit, memory, vault | M02/M07/M08 | test_audit::purge, test_memory::delete, test_vault::delete |
| R1 | Interface: tools, stream, vision flag, ctx, health, metrics (§7.1) | engine/base | M03 | test_engine::contract (fake + groq) |
| R2 | Groq end to end (§7.1) | engine/groq | M03 | live: test_groq_tool_call |
| R3 | KRY fallback warns (§2) | config | M00 | test_config::kry_fallback |
| R4 | 429 → user told + asked, no switch (§7.3) | orchestrator | M03 | test_orch::rate_limit_asks |
| R5 | Engine sees handles/redacted only (§7.3) | egress | M03 | test_egress::engine_payload_scan |
| R6 | No vision → OCR/UIA or BLOCKED (§7.1) | harness | M05 | test_harness::no_vision_path |
| R7 | Model choice measured + recorded (§7.1) | bench | M03 | docs/ofa/bench/engine-*.md |
| R8 | Swappable engine w/o orchestrator change (§7.1) | registry | M03 | test_engine::fake_swap |
| H1 | Discover installed/running apps (C2) | harness | M05 | test_discovery (windows) |
| H2 | open/close/focus/arrange verified by state (C2) | harness | M05 | test_c2 (Test Pad, windows) |
| H3 | Not installed / loading / ambiguous / dialog (C2) | harness | M05 | test_c2::failure_modes (fake) |
| H4 | Website open verified (C2) | browser hand | M05 | test_c2::browse_verified |
| H5 | System setting open; security change = Tier 2 (C2) | harness, tiers | M05 | test_c2::settings |
| H6 | Generic find/click/type/scroll (C3, §10.1) | harness api | M05 | test_c3 (Test Pad) |
| H7 | App with no adapter works (§13) | harness | M05 | user-run: Notepad/Settings script |
| H8 | Harness only via Gate (§10.1) | harness | M05 | test_no_bypass::harness |
| D1–D7 | Verbatim, script, punctuation, readback diff, low-conf confirm, compose loop, typing≠sending (C4) | dictation | M06 | test_dictation::* |
| G1–G6 | Criteria check, no near-match, exhausted, loop detect, interrupt, follow-up ref (C5, §3.3) | goal_loop, memory | M07 | test_goal::* , test_memory::resolve |
| I1–I7 | Session reuse, PM fill, Tier 1 explicit sign-in, ask account, handoff+resume, OTP permission, Tier 2 account/password (C6) | signin, broker | M08 | test_signin::* (mock pages) |
| F1–F7 | Field-by-meaning, no invention, ask+save, D2 ask, multi-page, validation, summary before submit (C7) | forms | M08 | test_forms::* (mock /mock/form) |
| L1–L6 | Permission before private search, 0/many matches, preview, hash-bound approval, verify attach (C8) | files_search | M08 | test_files::* |
| W1–W6 | Artifacts passed, per-dest status, partial failure report, no duplicate, unknown→check, repo read-only (C9) | workflow | M09 | test_workflow::* |
| P1–P6 | Complex detect, plan spoken, approval binds digest, revise→re-ask, material change pause, per-action T2 (C10) | planner | M09 | test_planner::* |
| Ph1–Ph3 | License evidence, local only/telemetry off, phone T2 via Gate (§10.2) | phone | M10 | 07 table + test_phone (optional) |
| X1 | ≥5 varied requests per C1–C10, ≥3 contexts (§13) | all | M11 | docs/ofa/bench/generalization-*.md (user-run) |
| X2 | Minimum surfaces list (§13) | all | M11 | same; unavailable → "untested" |
| X3 | Anti-hardcoding (§13) | all | M11 | test_no_hardcode (grep for contact/demo literals) |
| X4 | No false success (§13) | verify | M11 | test_verify::unknown_not_done |
| X5 | Latency + reliability targets (§9) | metrics | M11 | docs/ofa/bench/latency-*.md |
| X6 | Token discipline: caps + budget (§13) | docs | M11 | scripts/check_plan_caps.py |
| T2 | Stage 2 A1/A2/Engine UI (§7.2) | engine registry, web | M12 | deferred |

## Self-check result (Session P, 2026-11-26)
All §4–§10 requirements and §13 rows map to a row above. Gaps found and fixed during the check: kill switch mid-approval (A10), mic indicator (S9), no-vision path (R6), harness bypass (H8), loopback/auth (Q1), user data deletion (Q2), duplicate test id S1 in 04 → Q1. All files within caps with the 4-part header (checked by line count + grep). Open: B4/X1/X2 require the user (recordings, real apps).
