# OFA architecture, conventions and refactoring record

## Layout and ownership

```
one-for-all-api/
  ofa/                    voice-first assistant (Windows)
    __main__.py           command line entry
    runtime.py            builds the core and attaches the voice front end
    ports.py              VoicePort: the seam between the core and voice
    orchestrator.py       turn loop: user words -> engine -> tool calls -> spoken result
    tools.py              tool schemas and tool call -> Action mapping
    executor.py           policy gate: tier, approval, ledger, audit (decides, never performs)
    action_context.py     policy inputs read from the screen
    dictation.py          verbatim dictation rules
    effects/              what an authorised Action does (desktop, files, shell, credentials)
    policy/               tiers, yes-no lexicon, approvals
    vault/                encrypted store, handles, broker, password managers
    engine/               ReasoningEngine contract and adapters
    harness/              Windows UI Automation, OCR, input (and a fake for tests)
    speech/               Flux client, voice loop, routing
    text/                 Hindi numbers, transliteration, dictation text
    egress.py audit.py memory.py config.py live_budget.py orb.py server.py phone.py ui/
  voice/                  earlier Windows companion; ofa reuses its audio, providers, hotkey, DPAPI store
  ofa_execution/          earlier execution engine; ofa reuses its Windows primitives
  ebrain/ history/ oneforall/   product backend (shared memory and history APIs)
  tests/ofa_core/         OFA tests; tests/ holds the backend, voice and execution suites
```

## Dependency direction

`__main__ -> runtime -> orchestrator -> executor -> effects -> harness | vault`

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
| `ofa/executor.py` effect methods | `ofa/effects/{desktop,files,shell,credentials,scopes}.py` |
| `ofa/executor.py` `describe`, terminal list | `ofa/action_context.py` |
| `ofa/executor.py` dictation preparation | `ofa/dictation.py` |
| `ofa/runtime.py` `STT_ROUTES`, `stt_order` | `ofa/speech/routing.py` |
| `ofa/runtime.py` `holder` dict, patched executor attributes | `ofa/ports.py` |
| `tests/ofa/` | `tests/ofa_core/` |
| workspace `docs/` (outside the repo) | `docs/ofa/` |

## Remaining technical debt

- Two older runtimes (`voice` companion and `ofa_execution` engine) overlap with `ofa`. The web app's desktop
  pairing still uses them, so removing them needs a product decision and a web migration.
- `voice/` and `ofa_execution/` should eventually give their shared primitives to `ofa` as owned modules.
- `ofa/harness/api.py` and `ofa/harness/win.py` are large; split by reading, acting and identity when next changed.
- `ofa/orchestrator.py` builds the prompt, runs the loop and writes the report; extract the report builder.
- No dependency lock file for `requirements-ofa.txt`.
- The 30 Windows-only backend test failures and the web hotkey test need their own fixes.
