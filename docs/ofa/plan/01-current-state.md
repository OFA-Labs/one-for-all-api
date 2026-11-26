# 01 — Current State (discovered 2026-11-26)
**Purpose:** what exists and what we do with it · **Depends on:** §0.2, §12.1 Phase 0 · **Files likely touched:** none · **Done when:** M00 confirms these facts or logs deltas.

Facts below come from targeted reads in Session P. Repo docs were treated as claims, not truth; each "claim" row is re-verified in M00.

## Environment
| Fact | Evidence |
|---|---|
| OS: Windows 11 Home 10.0.26300, x64; Python 3.12.10; Git Bash + PowerShell 5.1 | `uname`, `python --version` |
| Root `voice-agents/` is NOT a git repo; `api/` and `web/` are | `COMMIT_POLICY.md`, `git` |
| api branch `fix/ebrain-ci-and-doc-cleanup`, 2 modified + 1 untracked E-Brain evidence files | `git status` |
| web branch `chore/ignore-local-workspace-artifacts`, 2 modified docs | `git status` |
| Keys: only `.env` exists; it has `GROQ_API_KRY` (typo), non-empty. No `GROQ_API_KEY`, `DEEPGRAM_API_KEY`, `GRADIUM_API_KEY` in env files or User/Machine env | awk names-only scan |
| Groq key valid: `GET /openai/v1/models` → 200 | 1 live call |
| Speech keys may be in DPAPI store `%LOCALAPPDATA%/OFA/voice/credentials.dat` (claim; `voice/__main__.py:206`) | code read |

## api/ (Python 3.12, FastAPI)
| Area | What it is | Decision | Reason |
|---|---|---|---|
| `voice/` (~3.4k lines) | Windows companion: Caps hook (`hotkey.py`), overlay orb (`overlay.py`), Deepgram nova-3 multi STT + `/v2/speak` TTS (`deepgram.py`), Gradium ASR/TTS ws (`gradium.py`), `failover.py`, HassIL grammar `intent.py`, pairing (P-256 + DPAPI), `protected_store.py`, speaker-mode capture gating, `LlmProvider` protocol unused | **Keep + modify** | Working mic→STT→action→TTS path (claim: user-confirmed 2026-11-25). Needs: persistent multi-turn session, 7 orb states, engine routing, Flux, echo guard, approval listening |
| `ofa_execution/` (~2.3k lines) | Serial `Engine` + `Gate`: typed `Plan/Step/Observation/Outcome`, `Hand` protocol, signed one-use step approvals bound to observation hash + epoch, emergency stop, takeover; hands: `windows.py` (UIA via comtypes, SendInput), `browser.py` (@opencode/browse 0.1.5), `files.py`, `slack.py`, `mcp.py` | **Keep core, modify Gate** | Already has the right shape (one-use, payload-bound, epoch). Gate becomes the enforcement point of the tiered approval engine (04); approvals must become *spoken*, not UI clicks |
| `ofa_execution/planner.py` | non-LLM planner | **Replace** by orchestrator + `ReasoningEngine` (06) | §7 |
| `ebrain/`, `tools/ebrain`, `migrations/` | Experimental memory, CI paused "project on hold" | **Leave untouched** | Out of scope; do not couple OFA to it |
| `voice/protected_store.py` | DPAPI blob store | **Reuse** inside vault key wrapping (05) | Already correct primitive |
| Separate venvs `.venv`, `.venv-voice`, `.venv-local-execution` | three requirement sets | **Modify**: add `requirements-ofa.txt` = voice ∪ local-execution ∪ new deps, one `.venv-ofa` | One runtime process |

## web/ (Next.js 16.4.6, React 19.3.1, Tailwind 4, Playwright)
| Area | Decision | Reason |
|---|---|---|
| Preview app with sample data; routes incl. `/arc-reactor` labelled **"OFA Engine"** in `src/components/layout/shell.tsx:85` | **Leave as is** | §0.1.1, §7.1 — deferred to M12 |
| `/voice-lab`, `/dictation`, `/connections`, `/settings` | Optional status display only (M11) | Orb is native, not web (C1) |
| `AGENTS.md`: Next.js 16 differs from training data — read `node_modules/next/dist/docs/` before web code | **Obey** | Repo rule |

## Do-not-touch (from COMMIT_POLICY, verified exists)
`web/docs/SPEC_ITERATION_1.md`, `web/AGENTS.md`, all README entry points, `tools/ebrain/legacy/**`, E-Brain implementation-plan files.

## Known claim conflicts to resolve in M00/M04
1. `docs/voice/README.md` says Deepgram Hindi TTS passed probes; Deepgram TTS docs read today list no Hindi voice (03).
2. Voice README points to a `feat/voice-pipeline` worktree as current; main checkout already contains `voice/` (PR #7). M00 picks the newest ref by `git log`, not by docs.
