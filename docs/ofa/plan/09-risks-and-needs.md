# 09 — Risks, Unknowns, User Needs
**Purpose:** what can stop us and what the user must provide · **Depends on:** all · **Files likely touched:** none · **Done when:** every "Need" is provided or marked untested.

## User must provide
| # | Need | When | Why |
|---|---|---|---|
| N1 | Rename `GROQ_API_KRY` → `GROQ_API_KEY` in `.env` (code accepts KRY with a warning meanwhile) | any time | §2 |
| N2 | `DEEPGRAM_API_KEY`, `GRADIUM_API_KEY` in `.env`, or confirm they are already in the DPAPI store | M00 | not found in env files |
| N3 | Which password manager (Bitwarden / 1Password / browser only / none) | M08 | 05 PM adapter |
| N4 | Windows Hello or a Windows password for vault unlock | M02 | §8.3 |
| N5 | ~60 benchmark recordings (consent) + 5 TTS ratings per provider | M04 | §4.2 |
| N6 | Test accounts / self-addressed destinations: WhatsApp self-chat, Slack test channel, Gmail to self, GitHub test repo, a job-platform test profile | M05–M11 | §12.2.7 |
| N7 | Preferred name + preferred script (Roman Hinglish default) + reply language | M01 | C1, §4.2 |
| N8 | Optional: Android phone with USB debugging for M10 | M10 | §10.2 |
| N9 | Decision: fast-path grammar on/off after M03 measurements | M03 | §7.3 |

## Risks
| Risk | Impact | Mitigation |
|---|---|---|
| Deepgram Hindi TTS not available (docs today show none) | Hindi replies degraded | M04 step 1 live check; degraded mode announced; report honestly |
| Groq free-tier limits (possibly 30 RPM / 8K TPM) | long tasks stall | header-based backoff, tell user + ask (no silent switch); compact context |
| gpt-oss no vision; qwen vision is preview | icon-only UIs blocked | UIA → OCR first; vision opt-in; mark BLOCKED_NO_VISION |
| gpt-oss no parallel tool calls | latency | sequential loop is acceptable; measure |
| No full AEC on speakers | echo/false barge-in | gating + echo guard; recommend headphones; WASAPI comms-mode AEC trial |
| Electron apps (WhatsApp, Slack, VS Code, Cursor) sparse UIA | C3 reliability | OCR fallback + adapters; web versions via browser |
| UIPI: elevated windows refuse input | partial control | handoff; never auto-elevate |
| Service terms restrict automation (WhatsApp, LinkedIn/job platforms, Gmail) | account restriction | prefer official APIs/sessions, human-paced actions, no bot-detection evasion; warn user per service before first use |
| Browser autofill can't be triggered programmatically | PM path limited | official PM CLIs; vault fallback |
| Windows Hello winrt binding availability on Python 3.12 | unlock UX | CredUI password fallback |
| E-Brain uncommitted changes in api checkout | checkout conflicts | M00 stashes them recoverably before branching |
| Docs in repos may be stale/hallucinated | wrong assumptions | M00 re-verifies the 01 claims by running, not reading |

## Platform limits (report in final)
Windows only. OCR text-only; DRM video black; secure desktop/UAC not automatable; iPhone surface impossible on Windows.

## Unknowns to resolve live
Deepgram Hindi TTS; Gradium language list; actual Groq limits from headers; WASAPI AEC availability; Windows OCR Hindi language pack installed?
