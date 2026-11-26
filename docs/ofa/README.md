# OFA core — voice-first laptop assistant (Windows)

Architecture and conventions: [ARCHITECTURE.md](ARCHITECTURE.md). Honest status: [CAPABILITY_REALITY.md](CAPABILITY_REALITY.md). Plan: [plan/](plan/00-INDEX.md). This page is the run book.

## Setup (once)

```powershell
cd one-for-all-api
uv venv --python 3.12 .venv-ofa
uv pip install --python .venv-ofa/Scripts/python.exe -r requirements-ofa.txt
```

Keys (names only, never commit values):

| Variable | Where | Notes |
|---|---|---|
| `GROQ_API_KEY` | `.env` in this folder (ignored by git) | `GROQ_API_KRY` (typo) is accepted with a warning |
| `DEEPGRAM_API_KEY`, `GRADIUM_API_KEY` | env, or the DPAPI store written by `python -m voice --save-speech-credentials` | already present on the dev machine |

Optional: `OFA_HEADPHONES=true` (enables barge-in), `OFA_EN_TTS=gradium`, `OFA_GROQ_MODEL`, `OFA_PORT` (default 8768).

## Run

```powershell
.venv-ofa/Scripts/python.exe -m ofa --env-file .env          # voice: press Caps Lock to talk
.venv-ofa/Scripts/python.exe -m ofa vault --env-file .env    # opens the local vault page
.venv-ofa/Scripts/python.exe -m ofa say --env-file .env "open notepad"
.venv-ofa/Scripts/python.exe -m ofa text --env-file .env     # typed REPL
.venv-ofa/Scripts/python.exe -m ofa doctor | audit | memory [forget KEY | clear]
```

The voice run prints a **Dashboard** link (`http://127.0.0.1:3000/ofa#port=8768&token=…`) for the web app
(`one-for-all-web`, `npm run dev`) and a **Vault** link. Both carry a per-process token in the URL fragment.

Typed text can never approve a consequential (Tier 2) action. Approvals are spoken: "yes / haan / bhej do".

## Test

```powershell
.venv-ofa/Scripts/python.exe -m pytest tests/ofa_core -q                          # fakes only, ~6 s
$env:OFA_WINDOWS_TESTS=1; .venv-ofa/Scripts/python.exe -m pytest tests/ofa_core/test_windows_real.py -q   # drives disposable windows
.venv-ofa/Scripts/python.exe scripts/bench_voice.py                          # voice benchmark (live, cached)
.venv-ofa/Scripts/python.exe scripts/e2e_live.py --env-file .env   # live generalization run
```

Live-call counts are capped in `ofa/live_budget.py` and recorded in `../docs/ofa/bench/live-calls.json`.

## Layout

| Module | Role |
|---|---|
| `ofa/policy/` | tiers, EN/HI/Hinglish yes-no lexicon, digest-bound single-use spoken approvals |
| `ofa/egress.py`, `ofa/audit.py` | leak canaries on every sink; hash-chained redacted audit |
| `ofa/vault/` | AES-GCM vault (DPAPI key, Windows Hello/password unlock), handles, broker, Bitwarden/1Password CLIs |
| `ofa/engine/` | `ReasoningEngine` contract, Groq, OpenAI-compatible user engine, fake |
| `ofa/harness/` | Windows UIA → OCR → (vision) helpers, SendInput, redacted screenshots |
| `ofa/executor.py`, `ofa/effects/`, `ofa/orchestrator.py`, `ofa/tools.py` | the only path from model to effects |
| `ofa/speech/` | Flux STT, persistent voice loop, echo guard |
| `ofa/orb.py`, `ofa/server.py`, `ofa/ui/` | orb, loopback API, vault page, mock forms |
| `ofa/phone.py` | optional Android-over-adb surface |
