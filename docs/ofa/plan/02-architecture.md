# 02 — Architecture
**Purpose:** components, data flow, layout, commands, targets · **Depends on:** §3, §9, 01 · **Files likely touched:** `api/ofa/**`, `api/voice/**`, `api/ofa_execution/**` · **Done when:** M01–M03 run one process end to end.

## Decisions
- **One native Windows process** `python -m ofa` (in api/) hosts voice, orchestrator, policy, broker, harness. Loopback FastAPI on `127.0.0.1:8767` (reuse companion port) for orb/vault UI + optional web status. No Electron.
- New package `api/ofa/` composes existing `voice/` and `ofa_execution/` as libraries. No second executor.
- Trust boundary: everything from the engine, websites, apps, harness, files is **untrusted data** (§8.7). Only two sources are trusted: the physical Caps key and mic speech verified by the approval listener (04).

## Components → modules
| Component (§9) | Module | Reuses |
|---|---|---|
| Voice layer | `voice/` + `ofa/voice_router.py` | deepgram.py, gradium.py, failover.py |
| Session manager | `ofa/session.py` (state machine, epoch counter) | voice/session.py, hotkey.py |
| Orb + frontend | `voice/overlay.py` (7 states) ; `ofa/ui/vault/*` (loopback page) | overlay.py |
| Reasoning adapter | `ofa/engine/{base,groq,fake}.py` | voice/contracts.LlmProvider (retire) |
| Orchestrator | `ofa/orchestrator.py` (§3.2 loop, tool registry) | — |
| Policy + approval | `ofa/policy/{tiers,approval,lexicon}.py` → enforced in `ofa_execution/policy.Gate` | Gate.sign/consume |
| Broker + vault | `ofa/vault/{store,handles,broker,pm_bitwarden,pm_1password}.py` | protected_store.py |
| Egress guard | `ofa/egress.py` (single chokepoint for LLM, logs, transcripts, audit, screenshots) | — |
| Execution tools | `ofa_execution/` hands + `ofa/harness/` (07) | windows.py, browser.py, files.py, slack.py, mcp.py |
| Verifier | `ofa/verify.py` (post-state checks per action kind) | ofa_execution/verification.py |
| Memory/profile | `ofa/memory.py` (SQLite: context, references, learned mappings; D0 only) | — |
| Audit log | `ofa/audit.py` (append-only JSONL, hash-chained, redacted) | — |

## Data flow (one turn)
```
Caps press → session.start(epoch++) → mic → STT stream (router) → final transcript
 → orchestrator: context + memory(D0) + tool schemas (handles only) → egress.guard → engine
 → tool_call(step) → policy.classify(tier) → [tier2: approval.ask() → TTS → listen → lexicon yes]
 → Gate.consume(token bound to digest(action,payload,dest,account)+epoch) → hand/harness/broker
 → verify → result (untrusted) → engine → spoken report → "Completed. Anything else?"
```
- The LLM never receives an approval token, a secret, or a D2 value. Tool results are wrapped `{"untrusted": true, "data": ...}`.
- Caps press while active → `session.stop()`: epoch++, all pending approvals and queued steps invalidated, hands told `stop()`.

## Tool surface exposed to the engine (finite verbs, generic targets — not a whitelist of apps)
`open(target)`, `close`, `focus`, `screen()`, `find_text`, `click(element_ref)`, `type_text(field_ref, text)`, `key`, `scroll`, `wait_for`, `browse(url)`, `read_file`, `search_files(scope)`, `fill(handle, field_ref)`, `send/submit/upload/...` (always Tier 2), `ask_user(question)`, `plan(steps)`, `remember(key, value)`.

## Tech choices (new deps; pin exact versions in M00)
`httpx` (Groq REST, OpenAI-compatible; no SDK needed) · `cryptography` (AES-GCM, already pinned) · `comtypes` (UIA, already) · `winrt-Windows.Media.Ocr` + `winrt-Windows.Security.Credentials.UI` (Windows OCR, Windows Hello) · `rapidfuzz` (echo similarity, fuzzy match) · `indic-transliteration` (Devanagari→Roman) · `pytest`, `pytest-asyncio`.

## Run commands (target, created in M00/M01)
```powershell
cd one-for-all-api
uv venv --python 3.12 .venv-ofa
uv pip sync --python .venv-ofa/Scripts/python.exe requirements-ofa.txt
.venv-ofa/Scripts/python.exe -m ofa --env-file .env      # live
.venv-ofa/Scripts/python.exe -m ofa --fake                            # all providers faked
.venv-ofa/Scripts/python.exe -m pytest tests/ofa -q -x -m "not live"
```

## Measurable targets (measured in M04/M11, results in `docs/ofa/bench/`)
| Metric | Target |
|---|---|
| End of speech → first ack audio (p50 / p95) | ≤ 0.9 s / 1.8 s |
| End of speech → first action start, simple task (one engine call) | ≤ 2.0 s p50 |
| Complex plan spoken aloud | ≤ 6 s p50 |
| Task success on generalization set (C2–C9) | ≥ 85 % |
| False "Completed" reports | 0 |
| Tier-2 executions without valid approval | 0 |
