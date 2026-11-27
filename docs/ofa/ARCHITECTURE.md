# OFA architecture, conventions and refactoring record

## Layout and ownership

```
one-for-all-api/
  ofa/                    voice-first assistant (Windows)
    __main__.py           command line entry
    runtime.py            builds the core
    companion.py          OfaBrain: plugs the core into the voice/ companion session and panel
    ports.py              VoicePort: the seam between the core and voice
    graphs/               the agent as LangGraph graphs (diagrams: GRAPHS.md)
      turn.py             one utterance -> control (pause/continue) or brain
      brain.py            engine <-> tools loop, references to new pop-ups, spoken report
      eyes.py             accessibility -> OCR -> vision provider, stops at the first confident answer
      hands.py            policy gate: tier, approval, effect, ledger, audit
      approval.py         spoken yes/no for one exact action
      pauses.py runner.py questions are interrupt()s; runner speaks them and resumes with the answer
      deps.py state.py report.py
    eyes/                 scene (numbered marks), masked capture, providers (local|separate|reasoning), attention
    settings_store.py     Eyes / Hands / Voice settings edited from the web Settings page
    tools.py              tool schemas and tool call -> Action mapping
    action_context.py     policy inputs read from the screen
    dictation.py          verbatim dictation rules
    effects/              what an authorised Action does (desktop, files, shell, credentials, system)
    policy/               tiers, yes-no lexicon, approvals
    vault/                encrypted store, handles, broker, password managers
    engine/               ReasoningEngine contract and adapters
    harness/              Windows UI Automation, OCR, input (and a fake for tests)
    speech/               Flux client, spoken controls, echo guard
    text/                 Hindi numbers, transliteration, dictation text
    egress.py audit.py memory.py config.py live_budget.py server.py phone.py ui/
  voice/                  the Windows companion and user interface: panel, Caps Lock, pairing, web API, audio
  ofa_execution/          earlier execution engine; ofa reuses its Windows primitives
  ebrain/ history/ oneforall/   product backend (shared memory and history APIs)
  tests/ofa_core/         OFA tests; tests/ holds the backend, voice and execution suites
```

## Dependency direction

`__main__ -> runtime -> graphs (turn -> brain -> eyes | hands -> approval) -> effects -> harness | vault`

- Rules stay plain modules the graph nodes call (`policy`, `dictation`, `action_context`, `effects`, `eyes`), so
  each is testable without a graph. Graphs only order them.
- Every question to the user is a LangGraph `interrupt()`. A node that asks does nothing before asking; every
  effect runs in its own node after approval, so resuming a saved task never repeats an action.
- Audio stays in `voice/session.py`: graphs receive finished sentences, never audio frames.
- Only `graphs/hands.py` runs effects and consumes approvals; `eyes/` never imports the vault.

- `policy`, `egress` and `audit` import nothing from the engine, speech or harness.
- Only `ofa/engine` talks HTTP to a model. `harness`, `speech`, `tools` and `phone` never import the vault.
- These rules are enforced by `tests/ofa_core/test_engine.py::test_no_bypass_import_rules`.

## Naming conventions

| Item | Python | TypeScript (web repo) |
|---|---|---|
| Files, folders | `snake_case.py` | `kebab-case.tsx`, feature folders under `src/features/` |
| Classes, interfaces, types | `PascalCase` | `PascalCase` |
| Functions, variables | `snake_case`, verbs for functions | `camelCase`; hooks `useThing` |
| Components | n/a | `PascalCase` component in a kebab-case file |
| Constants | `UPPER_SNAKE_CASE` | `UPPER_SNAKE_CASE` for module constants |
| Environment variables | `OFA_` prefix for OFA settings; provider keys keep the provider name | `NEXT_PUBLIC_` only for public values |
| API paths and events | `/kebab-case`; event kinds `snake_case` | same |
| Docs | new files `kebab-case.md`; existing upper-case names stay (tests and links pin some) | same |
| Commits, branches | `type(scope): summary`; `type/short-slug` | same |

Errors: raise a typed error carrying a short `CODE`; user-facing text is separate. Logging: the standard
`logging` module; every outbound sink passes `ofa.egress`.

## Dead code and dependency audit (2026-11-26)

Tools: `ruff` (pyflakes rules), `vulture`, `knip`.

| Finding | Class | Action |
|---|---|---|
| Unused Python imports, one duplicate dictionary key | A proven | removed |
| Three one-off nav-icon scripts in the web repo (no references) | A proven | removed |
| `vulture` hits in `ebrain/v3`, API models and settings fields | B investigate | kept: used through frameworks, serialisation or tests |
| Over-exported TypeScript symbols (used inside their own files) | C | kept |
| `extension/content.js` (referenced by the manifest), `review-motion.mjs` (documented) | C required | kept |
| `tools/ebrain/legacy`, `v3-eval` and `v3_eval` | C required | kept: frozen evidence and an intentional alias |
| Unused imports in `scripts/handoff_check.py` | C required | kept: they are an import smoke check |
| Unused dependencies | none found | |

## Baseline

| Check | Result before refactoring |
|---|---|
| API CI on `staging` (Linux E-Brain jobs, Windows voice job) | passing |
| `pytest tests` (without voice and execution) on the dev Windows machine | 30 failures already present on clean `staging`; CI passes |
| `tests/local_execution` real-desktop multistep test | failed before OFA work |
| Web `npm run verify` | 175 passed, 1 failed (`dictation-hotkey` focus), also failing on `staging`; 2 lint warnings |

## Migration log

| Old | New |
|---|---|
| `ofa/orchestrator.py` (turn loop) | `ofa/graphs/brain.py`, `ofa/graphs/report.py` |
| `ofa/executor.py` (policy gate) | `ofa/graphs/hands.py` |
| `ApprovalStore.obtain` (spoken loop) | `ofa/graphs/approval.py` |
| `OfaBrain` routing of pause / continue | `ofa/graphs/turn.py` |
| `ofa/executor.py` effect methods | `ofa/effects/{desktop,files,shell,credentials,scopes}.py` |
| `ofa/executor.py` `describe`, terminal list | `ofa/action_context.py` |
| `ofa/executor.py` dictation preparation | `ofa/dictation.py` |
| `ofa/runtime.py` `STT_ROUTES`, `stt_order` | `ofa/speech/routing.py` |
| `ofa/runtime.py` `holder` dict, patched executor attributes | `ofa/ports.py` |
| `tests/ofa/` | `tests/ofa_core/` |
| `ofa/orb.py`, `ofa/speech/loop.py`, `ofa/speech/routing.py` | removed: the companion panel and session are the front end |
| `ofa/server.py` dashboard endpoints | removed: the web app uses the companion API |
| workspace `docs/` (outside the repo) | `docs/ofa/` |

## Remaining technical debt

- The `ofa_execution` engine overlaps with `ofa`. The companion's fast path and the web app's approval cards
  still use it, so folding it into `ofa` needs a web change.
- OFA approvals are spoken only; the web app shows their text but its approve buttons act on `ofa_execution` tasks.
- `voice/` and `ofa_execution/` should eventually give their shared primitives to `ofa` as owned modules.
- `ofa/harness/api.py` and `ofa/harness/win.py` are large; split by reading, acting and identity when next changed.
- No dependency lock file for `requirements-ofa.txt`.
- Eyes verification after a click compares pixels near the click; it does not ask the vision model again.
- The 30 Windows-only backend test failures and the web hotkey test need their own fixes.
