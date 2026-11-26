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

Optional: `VOICE_HEADPHONES=true` (enables barge-in), `OFA_GROQ_MODEL`, `OFA_PORT` (vault page, default 8768).

## Run

```powershell
# API repo: the assistant (native top-middle panel + Caps Lock + OFA brain), companion API on 127.0.0.1:8767
.venv-ofa/Scripts/python.exe -m ofa --env-file .env
# Web repo: your frontend
npm run dev                                   # http://127.0.0.1:3000/desktop
```

1. Open `/desktop`, press **Connect computer** and approve the card on the panel (once per browser).
2. Press **Caps Lock** to start talking; press it again to stop. Say "yes / haan" or "no / nahi" when asked.
3. The panel input accepts typed requests. Typed text can never approve a consequential action.

Plain "open <app>" commands run on the companion's verified fast path without the model. Everything else goes
to OFA. Without a Groq key the companion runs only its built-in commands.

Other tools:

```powershell
.venv-ofa/Scripts/python.exe -m ofa vault --env-file .env    # local page for adding secrets
.venv-ofa/Scripts/python.exe -m ofa say --env-file .env "open notepad"
.venv-ofa/Scripts/python.exe -m ofa doctor | audit | memory [forget KEY | clear]
```

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
| `ofa/companion.py`, `ofa/speech/` | brain adapter for the companion session; Flux STT, spoken controls, echo guard |
| `ofa/server.py`, `ofa/ui/` | local vault page and mock forms |
| `ofa/phone.py` | optional Android-over-adb surface |
