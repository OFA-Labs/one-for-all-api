# CODEBASE_MAP — ONE FOR ALL (recon for the E-Brain Research Tournament)

Prepared by the neutral Recon agent on 2026-11-23 (IST), read-only. Nothing in the three repos was modified, installed, built, linted, formatted or tested.

How to read paths: every path that exists on disk is written with the "existing" prefix, a colon, then the path relative to c:\Users\jaiva\OneDrive\Desktop\voice-agents\ with forward slashes (example: `existing:one-for-all-web/src/app/page.tsx`). Line numbers follow the token as `L<start>-<end>`. Anything without that prefix does **not** exist today (or lives outside the workspace and is given as an absolute path).

Workspace root (`c:\Users\jaiva\OneDrive\Desktop\voice-agents\`) holds exactly four folders: `one-for-all-web`, `one-for-all-api`, `local-voice-assistant`, `ebrain-tournament`. There is no workspace-level `CLAUDE.md`, `AGENTS.md`, `.claude/` or `.agents/` folder, and no `.previous-media-venv` folder (both are referenced by older files, see section 13).

---

## 1. Repos and stack

### 1.1 `existing:one-for-all-web` — Next.js frontend (git, GitHub `OFA-Labs/one-for-all-web`, private)

Frontend-only interactive preview: no auth, microphone, browser control, database, AI or third-party API (`existing:one-for-all-web/README.md` L13-17). Language TypeScript; framework Next.js App Router (Turbopack is the Next 16 default).

`existing:one-for-all-web/AGENTS.md` (L1-9) is the Next-generated block: "This is NOT the Next.js you know … Read the relevant guide in `node_modules/next/dist/docs/` before writing any code." It says `next dev` re-adds this block (source `existing:one-for-all-web/node_modules/next/dist/server/lib/generate-agent-files.js`). The bundled docs exist at `existing:one-for-all-web/node_modules/next/dist/docs` (475 Markdown files). Breaking changes there that matter to E-Brain work (checked):
- Middleware is renamed **Proxy** in Next 16 (`existing:one-for-all-web/node_modules/next/dist/docs/01-app/01-getting-started/16-proxy.md` L15). There is no `src/middleware.ts` or `src/proxy.ts` today.
- `params` and `searchParams` are Promises and must be awaited (`existing:one-for-all-web/node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md` L259-293). The codebase already does this (`existing:one-for-all-web/src/app/page.tsx` L4-10, `existing:one-for-all-web/src/app/tasks/[id]/page.tsx` L2-8).
- Turbopack is the default for dev and build (same file L102).
- Route handlers are documented at `existing:one-for-all-web/node_modules/next/dist/docs/01-app/01-getting-started/15-route-handlers.md` (none exist in the app yet).

Versions. "Declared" is from `existing:one-for-all-web/package.json`, "lock" from `existing:one-for-all-web/package-lock.json` (lockfileVersion 3), "resolved" from `node_modules/<pkg>/package.json`. All three match for every package checked. The package.json pins exact versions (no `^`/`~`).

| Package | Declared = lock = resolved | Role |
|---|---|---|
| next | **16.4.6** | framework |
| react / react-dom | 19.3.1 / 19.3.1 | UI |
| typescript | 6.0.3 | dev |
| tailwindcss / @tailwindcss/postcss | 4.3.5 / 4.3.5 | styling (dev) |
| tw-animate-css | 1.4.0 | animation utilities (dev) |
| @playwright/test (playwright, playwright-core) | 1.65.1 | test runner (dev) |
| @axe-core/playwright | 4.14.0 | a11y audits in tests (dev) |
| radix-ui | 1.8.1 | primitives behind shadcn/ui |
| lucide-react | 1.73.0 | icons |
| class-variance-authority | 0.7.1 | variants for ui primitives |
| clsx / tailwind-merge | 2.1.1 / 3.7.0 | `cn()` in `src/lib/utils.ts` |
| cn | 0.5.2 | separate npm "cn" package used by `src/components/ui/*` |
| @fontsource-variable/manrope, dm-sans | 5.3.0, 5.3.0 | self-hosted fonts |
| eslint / eslint-config-next | 9.39.5 / 16.4.6 | lint (dev) |
| dependency-cruiser | 17.4.3 | architecture rules (dev) |
| prettier | 3.10.1 | format (dev) |
| postcss | 8.5.33 | dev |
| @types/node, @types/react, @types/react-dom | 26.6.6, 19.3.0, 19.3.0 | dev |

`overrides`: `@typescript-eslint/typescript-estree` → `minimatch 11.0.8`. `"type": "module"`. `engines.node >=22.0.0`; `existing:one-for-all-web/.nvmrc` says `24`. Local toolchain observed: Node v24.16.0, npm 11.13.0.

**No state library** (zustand, redux, swr, @tanstack/react-query are absent from the lockfile). No data-fetching, ORM, auth or WebSocket library is installed.

Python in this repo (tooling only, for video preparation): `existing:one-for-all-web/.venv/pyvenv.cfg` = Python **3.12.10**; installed packages are only `imageio_ffmpeg 0.8.1` and `pip 26.3`, matching `existing:one-for-all-web/requirements-tools.txt` (`imageio-ffmpeg==0.8.1`). `.venv/` is gitignored.

### 1.2 `existing:one-for-all-api` — backend placeholder (git, GitHub `OFA-Labs/one-for-all-api`, private)

Exactly one tracked file: `existing:one-for-all-api/README.md` ("# one-for-all-api / Backend for ONE FOR ALL."). No language, framework, dependency or config files. GitHub reports `primaryLanguage: null`, description "ONE FOR ALL backend".

### 1.3 `existing:local-voice-assistant` — offline Python voice prototype (**not** a git repo)

`git rev-parse` fails: "not a git repository". It is a standalone terminal app: Microphone → Faster-Whisper Base → Qwen3 4B via Ollama → Kokoro 82M → speakers, fully offline (`existing:local-voice-assistant/README.md` L1-12). It has no link to the web app or the API.

- Python: `existing:local-voice-assistant/.venv/pyvenv.cfg` = **3.12.10** (home `C:\Users\jaiva\AppData\Local\Programs\Python\Python312`, which exists; the venv was created from `voice-agents\.previous-media-venv\Scripts\python.exe`, which no longer exists).
- Declared deps, `existing:local-voice-assistant/requirements.txt`: torch==2.15.0+cpu, kokoro==0.9.4, faster-whisper==1.2.1, av==16.1.0, sounddevice==0.5.6, soundfile==0.14.0, numpy==2.5.5, requests==2.34.2, espeakng-loader==0.2.4, psutil==7.2.2, pytest==9.2.0.
- Resolved in `.venv/Lib/site-packages` (dist-info): the same versions for all of the above, plus transitive ctranslate2 4.9.0, misaki 0.9.4, spacy 3.8.18 (+ en_core_web_sm 3.8.0), transformers 5.23.0, huggingface_hub 2.4.0.
- External runtime: Ollama at `http://127.0.0.1:11434`, model `qwen3:4b` (README L11-12, `existing:local-voice-assistant/config.py` L32-33).

### 1.4 GitHub org OFA-Labs (`gh repo list OFA-Labs --limit 50`, read-only)

| Repo | Visibility | Default branch | Description | Created / pushed (UTC) |
|---|---|---|---|---|
| one-for-all-api | PRIVATE | main | ONE FOR ALL backend | 2026-11-23T01:09:22Z / 01:09:27Z |
| one-for-all-web | PRIVATE | main | ONE FOR ALL web frontend (Next.js) | 2026-11-23T01:08:36Z / 01:09:21Z |

Only these two repos exist. **There is no remote-only repo**, in particular no `one-for-all-core`, although the spec names the backend `one-for-all-core` (`existing:one-for-all-web/docs/SPEC_ITERATION_1.md` L515, L531, L562).

---

## 2. Package managers and commands

### 2.1 one-for-all-web (npm; lockfile `package-lock.json`)

Scripts in `existing:one-for-all-web/package.json` L6-19:

| Script | Command | What it does / side effects |
|---|---|---|
| `dev` | `next dev --hostname 127.0.0.1` | Dev server on 127.0.0.1:3000. Rewrites `next-env.d.ts` and re-adds the AGENTS.md block. The user often has this running. |
| `build` | `next build` | Production build into `.next/`. Rewrites `next-env.d.ts`. |
| `preview` | `next start --hostname 127.0.0.1` | Serves the existing `.next` production build. |
| `lint` | `eslint .` | Flat config, see 4.3. |
| `typecheck` | `tsc --noEmit` | Strict TS over `**/*.ts(x)` (src, tests, scripts). |
| `check:arch` | `depcruise src --config .dependency-cruiser.cjs` | Architecture rules, see 4.4. |
| `test` | `playwright test` | Starts its own `npm run preview -- --port 3100` (needs a prior build). Overwrites 4 tracked PNGs in `docs/screenshots/`. |
| `test:ui` | `playwright test --ui` | Playwright UI mode. |
| `format` | `prettier --write src tests scripts *.ts *.mjs *.json` | Writes files. No Prettier config file, so Prettier defaults apply. |
| `docs:generate` | `node --experimental-strip-types scripts/generate-handoff.ts` | Regenerates `docs/BACKEND_HANDOFF.md` **and** `docs/proposed-contracts.json` from `src/lib/integrations.ts`. |
| `verify` | `typecheck && check:arch && lint && build && test` | Full gate. The README (L51) describes it without `check:arch`, but the script includes it. |
| `review` | `node scripts/review.mjs` | Axe + screenshot review against `ONE_FOR_ALL_PREVIEW_URL` or `http://127.0.0.1:3000`. Writes `docs/screenshots/*.png` and `docs/supplemental-review.json`. |

Other tooling:
- `existing:one-for-all-web/scripts/setup.ps1` (L1-20): creates `.venv` if missing, `pip install -r requirements-tools.txt`, `npm ci`, then `npx playwright install chromium` with `PLAYWRIGHT_BROWSERS_PATH=.cache/ms-playwright`.
- `existing:one-for-all-web/scripts/review-motion.mjs`: playback-smoothness probe against `http://127.0.0.1:3000/`. Writes `docs/screenshots/space-black-<width>.png` and `docs/MOTION_PLAYBACK_REVIEW.json`.
- `existing:one-for-all-web/scripts/process-video.py`: builds the orb video assets with imageio-ffmpeg from `voice-agents\Screen Recording 2026-11-15 160400.mp4`. That source file is not in the workspace today.
- `existing:one-for-all-web/scripts/home-coast-video.py`: builds the home background video. Its docstring says to run it with system Python (OpenCV, NumPy, Pillow), using FFmpeg from `.venv`.
- Playwright browsers are kept project-local in `existing:one-for-all-web/.cache/ms-playwright` (chromium-1255, chromium_headless_shell-1255, ffmpeg-1013, winldd-1007).

### 2.2 one-for-all-api

Nothing: no package manager, scripts or commands.

### 2.3 local-voice-assistant (pip + venv; no pyproject, setup.cfg, pytest.ini or tox.ini)

- Install (README L46-56): `py -3.12 -m venv .venv`, then the CPU torch wheel from `https://download.pytorch.org/whl/cpu` first, then `pip install -r requirements.txt`.
- Run: `existing:local-voice-assistant/run.ps1` (L1-10) runs `.venv\Scripts\python.exe main.py` from the script folder.
- Smoke test with real models and mocked playback: `existing:local-voice-assistant/_smoke.py`, run with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. `_*.py` files are gitignored by its `.gitignore`.
- Tests: `& .\.venv\Scripts\python.exe -m pytest tests -q` from the folder (README L121-124).

---

## 3. Directory layout

### 3.1 one-for-all-web (203 tracked files)

```text
one-for-all-web/
├── AGENTS.md  README.md  package.json  package-lock.json  tsconfig.json  next.config.ts
├── eslint.config.mjs  postcss.config.mjs  playwright.config.ts  components.json
├── .dependency-cruiser.cjs  .editorconfig  .gitattributes  .gitignore  .nvmrc  .env.example
├── requirements-tools.txt  next-env.d.ts (tracked)  tsconfig.tsbuildinfo (ignored)
├── .claude/settings.json        (tracked; commit/PR attribution only)
├── .vscode/settings.json        (tracked)
├── src/
│   ├── app/                      App Router
│   │   ├── layout.tsx  page.tsx  error.tsx  loading.tsx  not-found.tsx  icon.svg
│   │   ├── providers/            app-provider.tsx (useApp context)  theme-provider.tsx
│   │   ├── about/ arc-reactor/ connections/ dictation/ e-brain/ extension/ handoff/
│   │   ├── history/ onboarding/ playground/ privacy/ reader/ recover/ settings/
│   │   ├── sign-in/ sign-up/ voice-lab/ watchers/         (each: page.tsx only)
│   │   └── tasks/[id]/page.tsx
│   ├── features/                 one folder per product area; index.ts barrel + components/
│   │   ├── account/      index.ts  components/account.tsx (AuthScreen, Onboarding)
│   │   ├── arc-reactor/  index.ts  components/arc-reactor.tsx
│   │   ├── connections/  index.ts  components/connections.tsx
│   │   ├── e-brain/      index.ts  components/e-brain.tsx            <- placeholder
│   │   ├── history/      index.ts  components/history-calendar.tsx + .css  lib/history-calendar.ts
│   │   ├── home/         index.ts  components/ofa.tsx ofa.css assistant.tsx reader.tsx home-video.tsx
│   │   ├── playground/   index.ts  components/playground.tsx          <- Agents registry
│   │   ├── reference/    index.ts  components/reference-pages.tsx (Handoff, Privacy, ExtensionPreview, About)
│   │   ├── settings/     index.ts  components/settings.tsx
│   │   │                 components/dictation/{dictation-chrome,dictation-provider,dictation-workspace}.tsx dictation.css
│   │   │                 types/dictation-context.ts
│   │   ├── voice-lab/    index.ts  components/voice-lab.tsx
│   │   └── watcher/      index.ts  components/watchers.tsx
│   ├── components/
│   │   ├── common.tsx            PageTitle, Pill, IntegrationButton, Notice, EmptyState, SectionLink, FlagButton, VoiceVideo, TrustLine
│   │   ├── layout/               shell.tsx (nav + chrome)  theme-selector.tsx
│   │   ├── reactor/              reactor-visual.tsx
│   │   ├── tasks/                task-workspace.tsx  task-detail.tsx  browser-decks.tsx  browser-decks.css
│   │   └── ui/                   shadcn primitives: button checkbox dialog input switch tabs textarea (.tsx)
│   ├── lib/
│   │   ├── demo.ts               domain types + sample scenarios + historyRows + task state machine
│   │   ├── integrations.ts       backend-handoff feature registry (30 features)
│   │   ├── browser-history.ts    tab-capture derivation for browser decks
│   │   ├── utils.ts              cn, segmentText, downloadFile
│   │   ├── dictation/            contracts.ts  hotkey.ts  mock-services.ts  model.ts
│   │   └── reactor/              reactor-beat.ts  reactor-transition.ts
│   ├── config/themes.ts
│   └── styles/globals.css        Tailwind entry + design tokens (4760 lines)
│   (no src/hooks/ folder, although components.json and the cruiser rules name it)
├── tests/                        15 flat Playwright specs (see section 7)
├── scripts/                      generate-handoff.ts review.mjs review-motion.mjs setup.ps1 process-video.py home-coast-video.py
├── docs/
│   ├── SPEC_ITERATION_1.md (965 lines, current spec)  SOURCE_SPEC.md (955, earlier copy)
│   ├── BACKEND_HANDOFF.md (generated)  proposed-contracts.json (generated)
│   ├── COVERAGE_MATRIX.md IMPLEMENTATION_PLAN.md EXECUTION_REPORT.md CHANGE_REPORT.md
│   ├── DESIGN_SYSTEM.md THEME_REFRESH.md MOTION_REFRESH.md VIDEO_ASSET.md ARC_REACTOR_MOTION.md GRADIUM_FEEDBACK.md
│   ├── dependencies.json dependency-audit.json supplemental-review.json MOTION_PLAYBACK_REVIEW.json
│   ├── assets/team-six7.png
│   ├── screenshots/ (10 png; 4 rewritten by tests, 4+2 by review scripts)
│   └── dictation/  ARCHITECTURE_NOTES STATUS DECISIONS REPORT MANUAL_QA INTEGRATION_HANDOFF (.md)
│                   *_OUTPUT.txt, UI_QA_OUTPUT.json, screenshots/ (15 png)
├── design-system/one-for-all/    MASTER.md (214 lines)  pages/workbench.md (overrides)
└── public/media/                 e-brain.png (236x236)  arc-reactor.png (2258x3739)
                                  ofa-engine-heart.mp4 + -poster.webp  watcher-eye.webm/.mp4 + -poster.webp
                                  one-for-all-{4k,1080p}.mp4 -poster.webp -captions.vtt asset-manifest.json
                                  home-coast-{4k,1080p}.mp4 -poster.webp -manifest.json
Untracked or ignored, present locally: node_modules/ .next/ .venv/ .cache/ artifacts/ .promptible/ test-results/
```

### 3.2 one-for-all-api

```text
one-for-all-api/
└── README.md
```

### 3.3 local-voice-assistant

```text
local-voice-assistant/
├── main.py (terminal UI, entry)  config.py (LVA_* env settings)  run.ps1  _smoke.py
├── requirements.txt  README.md  .gitignore
├── src/  __init__.py  recorder.py  transcriber.py  llm.py  synthesizer.py  pipeline.py
├── tests/ conftest.py  test_llm.py  test_pipeline.py  test_synthesizer.py  test_transcriber.py
├── audio/ kokoro_test.wav  last_response.wav
└── .venv/  .pytest_cache/  __pycache__/
```

---

## 4. Conventions (one-for-all-web)

### 4.1 Naming and file patterns
- Files and folders use kebab-case (`history-calendar.tsx`, `reactor-transition.ts`, `e-brain/`). Components are PascalCase **named** exports (`export function ArcReactor()`). Default exports appear only in Next route files (`page.tsx`, `layout.tsx`, `error.tsx`, `loading.tsx`, `not-found.tsx`).
- A feature is `src/features/<area>/index.ts` (a one-line barrel), plus `components/<area>.tsx`, optional `lib/` and `types/`, and optionally a CSS file imported by the component. Example: `existing:one-for-all-web/src/features/e-brain/index.ts` L1 `export { EBrain } from "./components/e-brain";`.
- Route files are thin server components. They import the barrel (`@/features/<area>`), optionally `export const metadata: Metadata = { title: "…" }` (the root template is `"%s · ONE FOR ALL"`, `existing:one-for-all-web/src/app/layout.tsx` L11-19), and render one component. One exception: layout.tsx deep-imports `DictationProvider` on purpose (L8-10).
- Some route and folder names differ: route `/watchers` maps to feature folder `watcher`; route `/arc-reactor` and folder `arc-reactor` are labelled "OFA Engine" in the UI.
- Interactive components start with `"use client"`.

### 4.2 TypeScript (`existing:one-for-all-web/tsconfig.json`)
`strict: true`, target ES2022, `module: esnext`, `moduleResolution: bundler`, `jsx: react-jsx`, `noEmit`, `allowJs`, `isolatedModules`, `resolveJsonModule`, `allowImportingTsExtensions` (used by `scripts/generate-handoff.ts`, which imports `../src/lib/integrations.ts`), `incremental`, plugin `next`. **Path alias `@/*` → `./src/*`** (L18). It includes `.next/types/**` and `.next/dev/types/**` and excludes `node_modules` and `.venv`. `existing:one-for-all-web/next-env.d.ts` is tracked and imports `./.next/dev/types/routes.d.ts`.

### 4.3 Lint and format
- `existing:one-for-all-web/eslint.config.mjs` (L1-15): flat config with `eslint-config-next/core-web-vitals` and `eslint-config-next/typescript`. It ignores `.next/**`, `out/**`, `.venv/**`, `test-results/**`, `playwright-report/**` and `next-env.d.ts`.
- `existing:one-for-all-web/.editorconfig`: utf-8, LF, 2-space indent, final newline, trim trailing whitespace (not for `*.md`). `*.py` and `*.ps1` use 4 spaces. `existing:one-for-all-web/.gitattributes`: `* text=auto eol=lf`, `*.ps1 eol=crlf`.
- Prettier 3.10.1 runs with defaults (no `.prettierrc` file).

### 4.4 Architecture boundaries — `existing:one-for-all-web/.dependency-cruiser.cjs` (run by `npm run check:arch`)

| Rule (lines) | From | Forbidden to | Meaning |
|---|---|---|---|
| `no-cross-feature-imports` L12-19 | `^src/features/([^/]+)/` | `^src/features/` except the same feature | A feature never imports another feature. Shared code moves to `components/`, `lib/` or `config/`. |
| `shared-must-not-import-features` L20-27 | `^src/(components\|hooks\|lib\|config)/` | `^src/features/` | Shared layers stay feature-agnostic. |
| `no-circular` L28-34 | any | circular | No cycles. |
| `no-orphans` L35-49 | orphan modules | — | Every module must be imported. Exempt: `*.d.ts` and Next entry files (`page|layout|template|error|global-error|loading|not-found|default|route` `.ts(x)`, at the root of `src/app/` or nested). |

Options: `includeOnly: "^src/"` (tests and scripts are not checked), `tsPreCompilationDeps: true`, tsconfig-aware (so `@/` aliases resolve), extensions `.ts .tsx .js .mjs .cjs .css .json`.

Allowed edges actually in use:
- `app/` → features, components, lib, config.
- features → components, lib, config, `@/app/providers/app-provider`.
- components → lib, config, `@/app/providers/*` (components → app is not forbidden; `components/common.tsx` L20 and `components/layout/shell.tsx` L35 import `useApp`).
- `features/reference` → `@/components/layout/shell` (`Brand`).
- A feature imports its own internals through either `./` or `@/features/<same>/…` (e.g. `existing:one-for-all-web/src/features/history/components/history-calendar.tsx` L28).

What this means for E-Brain:
- An e-brain feature may not import playground, history or watcher code. The Agent type and `sampleAgents` live inside `features/playground/components/playground.tsx` (L29-57), and the watcher list inside `features/watcher/components/watchers.tsx` (L22-34). Anything shared must first move to `src/lib/`, `src/components/` or a provider.
- Any new non-route module must be imported somewhere, or `no-orphans` fails.
- A new `src/app/**/route.ts` is exempt from the orphan rule.

### 4.5 Component and state patterns
- **One app-wide React context**: `AppProvider` / `useApp()` in `existing:one-for-all-web/src/app/providers/app-provider.tsx`.
  - `AppContext` type L44-74 (not exported); `useApp` L111-115; provider value L375-405.
  - Holds the role, onboarding flag, the current `task` (a `useReducer` over `createTask`/`transition` from `lib/demo.ts`, L227-246), toast `notify`, the `integrate(featureId, preview?)` gate (L322-332, which **throws on an unknown feature id**), watcher `notifications`, spoken-line `flags`, the Arc Reactor controller, and `reset()` (L363-372).
  - Nesting in `layout.tsx` L36-42: `ThemeProvider > AppProvider > DictationProvider > Shell`.
- `useSyncExternalStore` handles localStorage-backed values (role and onboarding L196-210; theme `existing:one-for-all-web/src/app/providers/theme-provider.tsx` L31-59; reduced motion `existing:one-for-all-web/src/lib/reactor/reactor-transition.ts` L37-44).
- Feature registries (Playground agents, watchers, Arc Reactor GO PRO routing) are **component-local `useState`**. The Shell renders `<main key={pathname}>` (`existing:one-for-all-web/src/components/layout/shell.tsx` L613), so page components remount on every route change. Inferred from code: that local state resets on navigation as well as on reload. AppProvider state survives client navigation because the provider sits in the root layout.
- Window events used as a bus: `ofa:session-change` (app-provider L79, L217, L225) and `ofa:reset-local-preview` (dispatched L364, consumed in `features/settings/components/dictation/dictation-provider.tsx` L174-175).
- Browser storage keys:

| Key | Where it is written |
|---|---|
| `one-for-all-role` | localStorage, app-provider L77 |
| `one-for-all-onboarding-complete` | localStorage, app-provider L78 |
| `one-for-all-preview-task` | localStorage, app-provider L76 |
| `one-for-all-theme` | localStorage, `existing:one-for-all-web/src/config/themes.ts` L14 |
| `one-for-all-preview-preferences` | localStorage, Settings `existing:one-for-all-web/src/features/settings/components/settings.tsx` L61-63 |
| `one-for-all-dictation-preview-v1` | sessionStorage, dictation-provider L30 |

  Playwright seeds `one-for-all-role=member` and `one-for-all-onboarding-complete=true` (`existing:one-for-all-web/playwright.config.ts` L15-26).
- Page skeleton: `<PageTitle title description action/>`, then `<Notice>`, then `<section className="panel">` blocks. Shared helpers live in `existing:one-for-all-web/src/components/common.tsx`: PageTitle L23-41, Pill L42-50, IntegrationButton L51-65, Notice L66-79, EmptyState L80-99.
- Every preview action tells the user that nothing real happened (a toast through `notify`). "Integration details" buttons call `integrate(id)` and open the handoff dialog built from `src/lib/integrations.ts`.

### 4.6 Styling
- Tailwind CSS 4 runs through `existing:one-for-all-web/postcss.config.mjs` (`@tailwindcss/postcss`). There is no tailwind.config: `components.json` has `"config": ""`, so tokens are set in CSS.
- `existing:one-for-all-web/src/styles/globals.css`:
  - `@import "tailwindcss"` and `@import "tw-animate-css"` (L1-2).
  - `@theme inline` maps the shadcn tokens to app tokens (L4-27).
  - Three themes via `[data-theme="obsidian"|"titanium"|"aurora"]` with `--t-*` tokens (L33-130). Theme ids live in `src/config/themes.ts`; a bootstrap script in `layout.tsx` L23 sets the theme before first paint.
- Most UI uses **semantic global classes** defined in globals.css (`.panel` L803, `.page-title` L782, `.empty-state` L864, `.pill`, `.notice`, `.nav-link`, `.nav-image-icon` L497-506). Tailwind utilities are used sparingly (`mt-6`, `flex flex-wrap gap-2`, …). Some features import their own CSS: `ofa.css`, `history-calendar.css`, `browser-decks.css`, `dictation.css`.
- shadcn/ui "new-york" style, `rsc: true`, baseColor slate, `iconLibrary: lucide`, aliases `@/components`, `@/components/ui`, `@/lib`, `@/lib/utils`, `@/hooks` (`existing:one-for-all-web/components.json`). The primitives in `src/components/ui/*` import `cn` from the npm package `"cn"`; app code imports `cn` from `@/lib/utils` (`existing:one-for-all-web/src/lib/utils.ts` L3-5).
- Visual direction is monochrome and pitch black (`existing:one-for-all-web/design-system/one-for-all/pages/workbench.md`, `existing:one-for-all-web/docs/THEME_REFRESH.md`). `tests/theme.spec.ts` asserts exact surface colours per theme, and `tests/video.spec.ts` L89-109 asserts a black body with no background image on several routes.

### 4.7 Icons, images, media
- Icons are lucide-react components: `import { Atom } from "lucide-react"`, rendered as `<Icon size={n} aria-hidden="true" />`. Nav items carry a `LucideIcon` (shell.tsx L46-51).
- Images and videos are referenced by root-absolute strings under `public/media`, e.g. `"/media/e-brain.png"`. They render through `next/image` `<Image>` (often `unoptimized`) or a raw `<video>` with `/media/*.mp4|webm` sources and `?v=` cache-busting queries (`existing:one-for-all-web/src/components/reactor/reactor-visual.tsx` L15-16, `existing:one-for-all-web/src/components/common.tsx` L228-258).
- The app icon is `existing:one-for-all-web/src/app/icon.svg`. Fonts are `@fontsource-variable/manrope` and `dm-sans`, imported in layout.tsx L2-3.

---

## 5. Routing and sections

Navigation is defined once in `existing:one-for-all-web/src/components/layout/shell.tsx`:
- `nav: NavItem[]` L63-80, rendered in the sidebar (L352-426), the mobile dialog (L628-645) and the mobile bottom nav (L734-746).
- `NavIcon` L156-172 picks the icon: `/arc-reactor` renders `<ReactorVisual compact/>`, `/watchers` renders `<WatcherEye/>`, items with `image` render `<Image className="nav-image-icon">`, everything else renders the lucide icon.
- The breadcrumb shows `active?.name` or a fallback map (L556-575).
- Route guard: everything except `/sign-in`, `/sign-up`, `/recover`, `/onboarding`, `/privacy` (L55-61) redirects visitors to `/sign-in` and incomplete onboarding to `/onboarding` (L277-282).
- Secondary nav (Connections, Settings, Developer handoff) is hardcoded at L439-464.

| Section | Route / page file | Main component(s) | Nav entry (shell.tsx) | Icon | State |
|---|---|---|---|---|---|
| **Home** | `/` `existing:one-for-all-web/src/app/page.tsx` (awaits `searchParams.mode`; `read` opens Reader) | `OFA` `existing:one-for-all-web/src/features/home/components/ofa.tsx` L33 (Ask/Read tabs L204-208, `#ofa-workspace` L161); `Assistant` `existing:one-for-all-web/src/features/home/components/assistant.tsx` L45 (typed request → `interruptionPreview` → `classifyPreview` → `start`, L58-76); `Reader` `existing:one-for-all-web/src/features/home/components/reader.tsx` L21; `HomeVideo`; task UI `existing:one-for-all-web/src/components/tasks/task-workspace.tsx` | L64 `{ href: "/", name: "Home", icon: AudioLines }` | lucide AudioLines | AppProvider `task` reducer (persisted to localStorage); local session/orb state. `/` is "immersive": the sidebar fades in on scroll (shell.tsx L225-256). `/reader` redirects to `/?mode=read#ofa-workspace` (`existing:one-for-all-web/src/app/reader/page.tsx`). |
| **Playground** (incl. **Agents** tab) | `/playground` `existing:one-for-all-web/src/app/playground/page.tsx` | `Playground` `existing:one-for-all-web/src/features/playground/components/playground.tsx` L71. Tabs `tasks` / `agents` L173-177. Task previews L178-211 (scenarios from `lib/demo.ts`). **Agents** L212-436. | L65 `{ href: "/playground", name: "Playground", icon: Boxes }` | lucide Boxes | Agents registry is local `useState` (see below). |
| **History** | `/history` `existing:one-for-all-web/src/app/history/page.tsx`; detail route `/tasks/[id]` `existing:one-for-all-web/src/app/tasks/[id]/page.tsx` | `HistoryCalendar` `existing:one-for-all-web/src/features/history/components/history-calendar.tsx` L256 (day/week/month/year, time-zone select, search and status filter L280-286, detail modal using `TaskDetail`). Calendar maths in `existing:one-for-all-web/src/features/history/lib/history-calendar.ts`. Detail `existing:one-for-all-web/src/components/tasks/task-detail.tsx` L27. | L66 `{ href: "/history", name: "History", icon: History }` | lucide History | Read-only sample `historyRows` (`existing:one-for-all-web/src/lib/demo.ts` L452-523, 7 rows). Local `useState` for view, anchor, filters. Proposed backend `history.list` → `GET /v1/tasks` (`existing:one-for-all-web/src/lib/integrations.ts` L928-964). |
| **Watchers** | `/watchers` `existing:one-for-all-web/src/app/watchers/page.tsx` | `Watchers` `existing:one-for-all-web/src/features/watcher/components/watchers.tsx` L29 (type `Watcher` L22-28; list L31-34; create/edit dialog; lifecycle buttons L194-245) | L67 `{ href: "/watchers", name: "Watchers", icon: Bell }`. Renders `WatcherEye` (L86-155) plus an unseen count and a "Seen" button (L377-405). | Video `/media/watcher-eye.webm/.mp4` while notices are unseen, else poster `/media/watcher-eye-poster.webp` | Watcher list is local `useState`. Notices live in AppProvider `notifications` (app-provider L275-311; `addWatcherNotice`, `markSeen`, `markAllSeen`). Proposed `watchers.manage` feature in integrations.ts (from L810). |
| **Arc Reactor** (UI name **"OFA Engine"**) | `/arc-reactor` `existing:one-for-all-web/src/app/arc-reactor/page.tsx` (metadata title "OFA Engine") | `ArcReactor` `existing:one-for-all-web/src/features/arc-reactor/components/arc-reactor.tsx` L42. Visual `ReactorVisual` `existing:one-for-all-web/src/components/reactor/reactor-visual.tsx` L23. | L68-73 `{ href: "/arc-reactor", name: "OFA Engine", icon: Atom, image: "/media/arc-reactor.png" }` plus the power toggle `.arc-toggle` L406-424 | The declared `image` is **never rendered**: NavIcon L158-159 returns `<ReactorVisual compact/>`, which uses `/media/ofa-engine-heart-poster.webp` and `/media/ofa-engine-heart.mp4`. | Global reactor state in AppProvider (see below). GO PRO lock and routing are component-local. |
| **e-brain** | `/e-brain` `existing:one-for-all-web/src/app/e-brain/page.tsx` (L1-5, **no `metadata` export**, so the title is the default "ONE FOR ALL — A little less busywork") | `EBrain` `existing:one-for-all-web/src/features/e-brain/components/e-brain.tsx` L1-5 | L74-79 `{ href: "/e-brain", name: "e-brain", icon: Atom, image: "/media/e-brain.png" }` | `existing:one-for-all-web/public/media/e-brain.png` (236x236 PNG), rendered 19x19 (20 in the bottom nav) with class `nav-image-icon` (22x22 CSS) | None |

### 5.1 What the e-brain placeholder renders today
`EBrain()` returns `null`, with this comment at L1-2: "Intentionally blank. 'e-brain' is a placeholder top-level destination; the shared shell (navigation, header and footer) still wraps this route."

The user therefore sees:
- the full Shell: sidebar with the e-brain item active (`aria-current="page"`), topbar breadcrumb "Workspace / **e-brain**", the "Interactive preview" marker, role selector, notifications bell, theme selector, the preview banner and the privacy footer;
- an **empty** `<main id="main-content" class="main-content">`.

There is no `<h1>`. `tests/quality.spec.ts` L24-36 requires a visible `main h1` on every route in its list, so adding `/e-brain` to that list (L4-23) would fail until the page has an h1. **No test references `/e-brain`.**

Spec B4.3 (`existing:one-for-all-web/docs/SPEC_ITERATION_1.md` L281-287) requires e-brain to stay "an intentionally blank placeholder: its page renders no content". The earlier `docs/SOURCE_SPEC.md` has no B4.3 or B4.4 and no mention of e-brain.

### 5.2 Arc Reactor preview state, exactly
- **Controller**: `useReactorController(notify)` in `existing:one-for-all-web/src/lib/reactor/reactor-transition.ts` L48-107.
  - Phases: `ReactorPhase = "idle" | "activating" | "active" | "deactivating"` (L12).
  - Shape: `ReactorTransition = { phase, startedAt, duration, heartbeatAt }` (L13-18).
  - `toggle()` (L62-77) is ignored while transitioning. It starts `activating` for `REACTOR_STARTUP_MS = 3500` or `deactivating` for `REACTOR_SHUTDOWN_MS = 4200` (`existing:one-for-all-web/src/lib/reactor/reactor-beat.ts` L2-3). Under `prefers-reduced-motion` the duration is 180 ms.
  - A `setTimeout` effect (L79-100) settles the phase to `active` or `idle` and toasts "OFA Engine activated in this preview. No model or backend was connected." or "OFA Engine deactivated in this preview.".
  - `reset()` (L102-104) forces `idle`.
  - Labels: `reactorActionLabel` L20-25 (`ACTIVATE OFA ENGINE`, `INITIALIZING...`, `DEACTIVATE OFA ENGINE`, `POWERING DOWN...`).
- **Ownership**: AppProvider calls the controller (app-provider L314-318) and exposes `reactor`, `toggleArcReactor`, and `arcReactorActive = phase === "active" || phase === "deactivating"` (L320-321).
- **Lifetime**: in memory only, never written to storage. It survives client-side navigation (the provider is in the root layout) and is cleared by a reload or by **"Reset local demo now"** in the footer's "Delete my data" dialog (shell.tsx L703-733 → `reset()` app-provider L363-372 → `resetReactor()`).
- **Three controls toggle it**: the stage button (arc-reactor.tsx L98-109), the action button (L154-167) and the nav power toggle (shell.tsx L410-422). All carry `data-reactor-state`, which `existing:one-for-all-web/tests/arc-reactor.spec.ts` relies on (L3-8, L57-63).
- During `activating`, the Shell pulses a heartbeat "shake" translate on the sidebar, frame, toasts and mobile nav (shell.tsx L284-333). `ReactorVisual` drives CSS variables (`--reactor-presence`, `--reactor-mix`, `--reactor-light`, …) per animation frame without React state (reactor-visual.tsx L40-193).
- **Second panel** "Bring your second OFA Engine" (arc-reactor.tsx L178-262): `proUnlocked` and `routing` are local `useState` (L69-76). Default routing: code, refactor and deep go to `r1`; planning goes to `r2`. The task rules are at L14-35. The UI says "reset on reload"; per section 4.5 they also reset on route change.
- Spec and UI naming differ. B4.3 says "Arc Reactor" and "Arc R1"; the UI says "OFA Engine" and "OFA Engine R1/R2". The spec says the active state shows "the same smooth, infinite orb video that runs on the hero"; the code uses the dedicated `ofa-engine-heart.mp4` (`existing:one-for-all-web/docs/ARC_REACTOR_MOTION.md`).

### 5.3 Playground Agents registry, exactly (spec B4.4)
- Type `Agent = { id, name, description, file, instructions, triggers: string[] }` (playground.tsx L29-36). Two samples, "PR reviewer" (`pr-reviewer.md`) and "Research digest" (`research-digest.md`), at L38-57. `blankAgent()` L59-66; `newAgentId()` gives `agent-<ms>-<rand5>` (L68-69).
- State L76-81: `agents`, `draft`, `editingId`, `formOpen`, `agentError`.
- `saveAgent` L95-130 validates the name, the Markdown instructions and at least one trigger. The file name is derived as a slug of the name + `.md` when left blank.
- Trigger add/remove: L131-145. `loadInstructionFile` L146-155 reads a local `.md` through `File.text()` in the browser only.
- Card list with Edit/Remove and a "View Markdown instructions" `<details>`: L369-434.
- **Nothing consumes the triggers**: no code matches spoken or typed phrases to agents. The Home `Assistant.submit` (assistant.tsx L58-76) routes text only through `interruptionPreview` and `classifyPreview` (`existing:one-for-all-web/src/lib/demo.ts` L414-436).
- No test covers the Agents tab.

### 5.4 Other routes (all wrapped by Shell unless standalone)
| Route | File | Component |
|---|---|---|
| `/connections` | `existing:one-for-all-web/src/app/connections/page.tsx` | `Connections` |
| `/settings?tab=` | `existing:one-for-all-web/src/app/settings/page.tsx` | `SettingsPage` (tabs personal "Profile & facts", voice, dictation, safety, usage — settings.tsx L13-19, L90-96) |
| `/dictation` | `existing:one-for-all-web/src/app/dictation/page.tsx` | redirect to `/settings?tab=dictation` |
| `/handoff` | `existing:one-for-all-web/src/app/handoff/page.tsx` | `Handoff` (renders all integration features, `existing:one-for-all-web/src/features/reference/components/reference-pages.tsx` L33) |
| `/about`, `/privacy`, `/extension` | `existing:one-for-all-web/src/app/about/page.tsx`, `existing:one-for-all-web/src/app/privacy/page.tsx`, `existing:one-for-all-web/src/app/extension/page.tsx` | `About`, `Privacy` (public), `ExtensionPreview` |
| `/voice-lab` | `existing:one-for-all-web/src/app/voice-lab/page.tsx` | `VoiceLab` (owner-gated by preview role) |
| `/sign-in`, `/sign-up`, `/recover`, `/onboarding` | `existing:one-for-all-web/src/app/sign-in/page.tsx` etc. | `AuthScreen mode=…`, `Onboarding` (standalone, no sidebar) |

---

## 6. Data and state

- **No backend calls of any kind.** There are no route handlers (`route.ts`), no `"use server"` actions, no `fetch(`, `WebSocket`, `EventSource` or `process.env` anywhere in `src/`; only the string "Outgoing encrypted WebSocket…" appears, inside integrations.ts L416. `existing:one-for-all-web/tests/journeys.spec.ts` L210-228 **fails if any request leaves `http://127.0.0.1:3100/` or hits a `/v1/` path** during the PR journey. A real E-Brain client must account for this test.
- **Proposed backend contract (handoff registry)**: `existing:one-for-all-web/src/lib/integrations.ts`.
  - `type Feature` L1-21: `id, name, module, spec, purpose, frontend[], backend[], data, api{transport?: "http"|"local-adapter", method, path, auth, request, response}, rules[], success, errors[]`.
  - `features` array L23-1249 holds **30** entries. The last is `dictation.preview` L1199-1248; the array closes with `];` at L1249. `featureById` L1250-1252.
  - Ids: auth.email, auth.google, auth.recovery, voice.session, task.start, task.control, task.events, approval.commit, approval.question, browser.pair, browser.permissions, browser.disconnect, files.drive, files.upload, reader.speech, speech.flag, jobs.workflow, social.workflow, research.workflow, watchers.manage, connections.github, connections.telegram, history.list, settings.save, privacy.delete, voice.clone, speech.harness, stretch.sheets, stretch.desktop, dictation.preview. (`docs/COVERAGE_MATRIX.md` still says 29, written before dictation.)
  - Constraints from `existing:one-for-all-web/tests/domain.spec.ts` L67-81: unique ids; non-empty frontend, backend, errors and rules; `success.length > 15`; `api.path` must match `^/v1/` unless `transport: "local-adapter"`, in which case it matches `^src/.+\.ts — \w+$`.
  - Generated outputs, `existing:one-for-all-web/docs/BACKEND_HANDOFF.md` and `existing:one-for-all-web/docs/proposed-contracts.json`, come from `existing:one-for-all-web/scripts/generate-handoff.ts`. Its template, including the "Screen-to-feature map", is the single long string on L5.
  - Handoff "Integration order" item 2 says: "Generate shared wire types from FastAPI contracts, replacing illustrative client types." Spec B7.1 L531 says: "Shared message types are generated from the backend so they cannot drift." **No generated types exist today.**
- **Shared types** (hand-written):
  - `existing:one-for-all-web/src/lib/demo.ts`: `Role` L1, `ScenarioId` L2, `TaskStatus` L3-16, `OrbState` + `orbStates` L17-47, `Draft` L48-57, `scenarios` L68-207, `Task` L208-221, `TaskAction` L222-241, `createTask` L242, `transition` L263, `classifyPreview` L414, `interruptionPreview` L423, `statusToOrb` L437, `historyRows` L452-523.
  - `existing:one-for-all-web/src/lib/browser-history.ts` (`TabCapture`).
  - `existing:one-for-all-web/src/lib/dictation/contracts.ts`: the `DictationServices` interface L82-118 is the one existing "adapter seam" pattern (interface + `existing:one-for-all-web/src/lib/dictation/mock-services.ts` + `BACKEND NOT IMPLEMENTED` comments).
  - `existing:one-for-all-web/src/config/themes.ts` (`ThemeId`).
  - `existing:one-for-all-web/src/features/settings/types/dictation-context.ts`.
- **Mock data**: `scenarios`, `historyRows` (lib/demo.ts); `sampleAgents` (playground.tsx L38-57); watchers (watchers.tsx L31-34); notifications (app-provider L275-290); fictional profile facts (settings.tsx L21-33); mock dictation services; `SAMPLE_TRANSCRIPT = "Kal meeting hai, कृपया agenda भेज दो 🙂"` (contracts.ts L36).
- **Spec data model** (B8, SPEC_ITERATION_1.md L647-653) lists `profile_facts`, `tasks`, `task_events`, `conversation_messages`, `artifacts`, `watchers`, LangGraph checkpoint tables, etc., and says "The website never talks to the database directly; only the backend does." Spec B7.1 L524 places "Memory — profile facts, preferences, history" inside the backend. Roadmap B14.1 L773 schedules "Memory and ask budget" in Week 3 (4-10 Dec).
- **Env / config**:
  - The app reads **no** env vars. `existing:one-for-all-web/.env.example` (L1-3) has one name, `ONE_FOR_ALL_PREVIEW_URL` (tooling only, `scripts/review.mjs` L7). `.gitignore` ignores `.env*` except `.env.example`. No other `.env*` file was found in the three repos (none was opened).
  - `playwright.config.ts` sets `PLAYWRIGHT_BROWSERS_PATH`.
  - `existing:one-for-all-web/next.config.ts`: `{ poweredByHeader: false, devIndicators: false }` only.
  - local-voice-assistant env names (`existing:local-voice-assistant/config.py` L31-73): LVA_OLLAMA_HOST, LVA_OLLAMA_MODEL, LVA_OLLAMA_NUM_CTX, LVA_OLLAMA_TIMEOUT, LVA_OLLAMA_TEMPERATURE, LVA_MAX_HISTORY_MESSAGES, LVA_SYSTEM_PROMPT, LVA_OLLAMA_NUM_PREDICT, LVA_WHISPER_MODEL, LVA_WHISPER_DEVICE, LVA_WHISPER_COMPUTE_TYPE, LVA_WHISPER_LANGUAGE, LVA_WHISPER_VAD, LVA_CPU_THREADS, LVA_SAMPLE_RATE, LVA_TTS_SAMPLE_RATE, LVA_INPUT_DEVICE, LVA_OUTPUT_DEVICE, LVA_MAX_RECORD_SECONDS, LVA_BLOCK_SIZE, LVA_SILENCE_THRESHOLD, LVA_SILENCE_BLOCKS, LVA_MIN_SPEECH_BLOCKS, LVA_MIN_AUDIO_SECONDS, LVA_TTS_VOICE, LVA_TTS_LANG_CODE, LVA_TTS_SPEED. The README also uses HF_HUB_OFFLINE and TRANSFORMERS_OFFLINE.

---

## 7. Tests

### 7.1 one-for-all-web — Playwright only (there is no Jest or Vitest)
- Config `existing:one-for-all-web/playwright.config.ts`:
  - `testDir ./tests`, `fullyParallel`, `workers: 2`, `retries: 0`, timeout 45 s.
  - Reporters `list` + `html` (open: never; writes `playwright-report/`, gitignored).
  - `baseURL http://127.0.0.1:3100`; `storageState` seeds a signed-in member (L15-26); headless; `trace: retain-on-failure`; `screenshot: only-on-failure`; `reducedMotion: "reduce"`.
  - `webServer: npm run preview -- --port 3100`, `reuseExistingServer: false` (L32-37). This serves the existing `.next` build, so it needs `npm run build` first (`npm run verify` builds before testing).
  - One project: `chromium` at 1440x1000. Browsers come from `.cache/ms-playwright`.
- Commands: `npm test`, `npx playwright test tests/<file>.spec.ts`, `npm run test:ui`, `npm run verify`. (Recon ran none of them.)
- Location and naming: flat `tests/<area>.spec.ts`, 15 files, no fixtures folder. Helpers are local functions inside each spec. Two kinds:
  - **Browser journeys** use the `page` fixture.
  - **Pure domain tests** import from `../src/lib/...` without a browser: `domain.spec.ts`, `calendar-domain.spec.ts`, `dictation-model.spec.ts`, and parts of `video.spec.ts` / `home-video.spec.ts`.

| File | Covers |
|---|---|
| `existing:one-for-all-web/tests/arc-reactor.spec.ts` (604 lines) | OFA Engine phases, timings, shake, navigation persistence, reset, reduced motion |
| `existing:one-for-all-web/tests/assistant-stage.spec.ts` | Home orb stage |
| `existing:one-for-all-web/tests/browser-decks.spec.ts` | tab decks and capture dialog |
| `existing:one-for-all-web/tests/calendar.spec.ts`, `existing:one-for-all-web/tests/calendar-domain.spec.ts` | History calendar UI and maths |
| `existing:one-for-all-web/tests/dictation.spec.ts`, `existing:one-for-all-web/tests/dictation-model.spec.ts`, `existing:one-for-all-web/tests/dictation-hotkey.spec.ts` | Caps Lock dictation preview (axe in dictation.spec) |
| `existing:one-for-all-web/tests/domain.spec.ts` | demo state machine, interruption parser, **integrations registry shape** |
| `existing:one-for-all-web/tests/home-video.spec.ts`, `existing:one-for-all-web/tests/video.spec.ts`, `existing:one-for-all-web/tests/ofa.spec.ts` | media and O F A workspace |
| `existing:one-for-all-web/tests/journeys.spec.ts` | PR, pause and cancel, dialogs, Reader, signup, watcher, jobs, owner gating, **no-network check**, guest entry |
| `existing:one-for-all-web/tests/quality.spec.ts` | console errors and `main h1` on 18 routes (L4-23), axe WCAG 2 A/AA + 2.1 AA, responsive overflow at 375/768/1024/1440 (L59-84), **screenshots** (L85-120) |
| `existing:one-for-all-web/tests/theme.spec.ts` | three themes, persistence, no remount |

- Side effects: `quality.spec.ts` L85-120 **overwrites four tracked files**: `docs/screenshots/assistant-desktop.png`, `assistant-mobile.png`, `reader-tablet.png` and `connections-desktop.png`.
- Not covered by any test: `/e-brain`, `/arc-reactor` in the quality, a11y and responsive route lists, and the Playground **Agents** tab.
- **Known broken test** `existing:one-for-all-web/tests/dictation-hotkey.spec.ts` L95-120, "focus feedback explains another tab and returning focus keeps the shortcut usable".
  - Local evidence from the last run (2026-11-23 06:33 IST): `existing:one-for-all-web/test-results/.last-run.json` has `status: "failed"` with exactly one failed test.
  - `test-results/dictation-hotkey-focus-fee-1599c-s-keeps-the-shortcut-usable-chromium/error-context.md` shows `expect(getByTestId('dictation-shortcut-status')).toContainText("Page unfocused")` (L105-107) received `"Caps Lock detected · 1 press."` after `other.bringToFront()`.
  - The root cause in product code was not investigated (read-only recon).

### 7.2 local-voice-assistant — pytest 9.2.0
- Command: from `existing:local-voice-assistant`, run `& .\.venv\Scripts\python.exe -m pytest tests -q`. There is no pytest config file. `existing:local-voice-assistant/tests/conftest.py` L1-8 only puts the project root on `sys.path`.
- Files: `existing:local-voice-assistant/tests/test_llm.py` (12 node ids incl. 3 parametrized), `existing:local-voice-assistant/tests/test_pipeline.py` (7), `existing:local-voice-assistant/tests/test_synthesizer.py` (9), `existing:local-voice-assistant/tests/test_transcriber.py` (5). That makes **33** node ids in `.pytest_cache/v/cache/nodeids`; there is no `lastfailed` cache file. The tests mock hardware, Ollama, Whisper and Kokoro.

### 7.3 one-for-all-api — no tests.

---

## 8. Python side

### 8.1 local-voice-assistant (what it is, facts only)
- **Entry**: `existing:local-voice-assistant/main.py`, a terminal loop (L118-148). Controls are Enter to speak, `text`, `devices`, `in N`, `out N`, `reset`, `q` (L67-103). `build_pipeline()` warms up the models and probes the speaker (L43-64).
- **Modules** (`existing:local-voice-assistant/src`):
  - `existing:local-voice-assistant/src/recorder.py`: `Recorder` (L33) records push-to-talk with energy VAD and a 15 s cap; `RecorderError`.
  - `existing:local-voice-assistant/src/transcriber.py`: `Transcriber` (L30), lazy Faster-Whisper `base`/int8/CPU.
  - `existing:local-voice-assistant/src/llm.py`: `LLMClient` (L41) is a stateful Ollama `/api/chat` client. It keeps **in-memory** `history` (L62), trimmed to `MAX_HISTORY_MESSAGES = 10` (L160-162, config L37), and strips `<think>` blocks (L29-38). `OllamaError`.
  - `existing:local-voice-assistant/src/synthesizer.py`: `Synthesizer` (L36), Kokoro 82M with voice `af_heart` and lang `a`, 24 kHz WAV saved to `audio/last_response.wav`, with an output-drain probe.
  - `existing:local-voice-assistant/src/pipeline.py`: `VoicePipeline` (L52) with `warmup` L67, `process_audio` L81, `text_turn` L126, `turn` L156; `TurnResult` (L38) records STT/LLM/TTS latency and RSS.
- **Config**: `existing:local-voice-assistant/config.py`; every setting can be overridden through the `LVA_*` env vars (section 6). The system prompt (L39-44) asks for 1-2 sentences, at most 25 words, English.
- **Memory today**: only the last 10 messages, lost on exit (README L215-216). English only by default (README L217).
- Measured (per README L179-192): about 21 s per full turn on CPU; 33 tests passed.

### 8.2 one-for-all-api
README only (`existing:one-for-all-api/README.md`). It is the only place a Python service is meant to live, per the GitHub description "ONE FOR ALL backend" and handoff phrases such as "FastAPI contracts". The spec's architecture (B7.1, `existing:one-for-all-web/docs/SPEC_ITERATION_1.md` L506-531) describes this backend as `one-for-all-core`: FastAPI with Pipecat voice, LangGraph brain, workers, policy gate, connectors, watchers, Telegram and **Memory**, plus Postgres (Supabase) and Langfuse. None of it exists yet.

---

## 9. Existing agent-memory and instruction artifacts ("project memory" today)

| Artifact | Tracked? | What it holds |
|---|---|---|
| `existing:one-for-all-web/AGENTS.md` | yes | Only the Next-generated "This is NOT the Next.js you know" rule block (L1-9). |
| `CLAUDE.md` | — | **None** in any repo or at the workspace root. User-level `C:\Users\jaiva\.claude\CLAUDE.md` also does not exist. |
| `existing:one-for-all-web/.claude/settings.json` | yes | Only `attribution.commit` ("One For All" + Co-Authored-By noreply@one-for-all.local) and `attribution.pr` (team image `docs/assets/team-six7.png` + "**One For All**"). No commands, agents, hooks or skills folders. `.claude/settings.local.json` is gitignored and absent. |
| `existing:one-for-all-web/.vscode/settings.json` | yes | Python interpreter `.venv`; hides node_modules, .next, .cache, .venv. |
| `existing:one-for-all-web/README.md` | yes | Stack, setup, scripts, structure, architecture rules, deploy. Warns that dated docs mention old paths (L111). |
| `existing:one-for-all-web/docs/SPEC_ITERATION_1.md` | yes | **The current product spec** (965 lines): Parts A-E. Includes B4.3/B4.4 (sections, e-brain, Agents), B7 architecture, B8 data model, B14 roadmap. |
| `existing:one-for-all-web/docs/SOURCE_SPEC.md` | yes | Earlier copy of the same spec (955 lines, without B4.3/B4.4). |
| `existing:one-for-all-web/docs/BACKEND_HANDOFF.md` / `existing:one-for-all-web/docs/proposed-contracts.json` | yes | Generated from integrations.ts: integration order, roles, event envelope, orb precedence, error codes, and every feature contract. |
| `existing:one-for-all-web/docs/COVERAGE_MATRIX.md`, `existing:one-for-all-web/docs/IMPLEMENTATION_PLAN.md`, `existing:one-for-all-web/docs/EXECUTION_REPORT.md`, `existing:one-for-all-web/docs/CHANGE_REPORT.md` | yes | Dated build reports: spec→UI coverage, route/role inventory, first-build results, visual refresh. Some paths predate the 22 Nov restructure. |
| `existing:one-for-all-web/docs/DESIGN_SYSTEM.md`, `existing:one-for-all-web/docs/THEME_REFRESH.md`, `existing:one-for-all-web/docs/MOTION_REFRESH.md`, `existing:one-for-all-web/docs/VIDEO_ASSET.md`, `existing:one-for-all-web/docs/ARC_REACTOR_MOTION.md`, `existing:one-for-all-web/docs/GRADIUM_FEEDBACK.md` | yes | Visual, motion and media decisions; Gradium feedback template (no real calls). |
| `existing:one-for-all-web/docs/dictation` | yes | A full agent work log for the dictation feature: STATUS (checkpoints), DECISIONS, ARCHITECTURE_NOTES (references the pre-restructure `src/components/provider.tsx`), REPORT, MANUAL_QA, INTEGRATION_HANDOFF, captured command outputs (*_OUTPUT.txt) and 15 screenshots. It is the closest existing example of agent-written, human-readable project memory. |
| `existing:one-for-all-web/design-system/one-for-all/MASTER.md` + `existing:one-for-all-web/design-system/one-for-all/pages/workbench.md` | yes | Design-system master rules. `pages/*.md` overrides the master (MASTER.md L3-5); workbench.md holds the current monochrome overrides. |
| `existing:one-for-all-web/.promptible` | no (gitignored) | Output of a motion-design agent workflow for the reactor (19 Nov): research-brief.md, reference-observations.md, render-brief.json (status AWAITING_CRITIC; references `voice-agents\.agents\skills\motion-graphics\…`, which no longer exists), critic.json (verdict pass), capture-reactor.mjs, PNG/WebM/MP4 evidence. |
| `existing:one-for-all-web/artifacts` | no (gitignored) | Large media work products: home-video (including mkv files of ~145 MB and ~287 MB), ofa-engine QA PNGs + visual-qa.json, ofa-media sheets. |
| `existing:one-for-all-web/.cache` | no (gitignored) | `ms-playwright` browsers plus agent QA snapshots: before/after copies of source files (deck-before, monochrome-before, ofa-before), QA screenshots, two ad-hoc playwright configs, motion render scripts, original-orb. |
| Claude Code auto-memory `C:\Users\jaiva\.claude\projects\c--Users-jaiva-OneDrive-Desktop-voice-agents\memory\` | outside repos | Folder exists. Files (names only): `MEMORY.md`, `attribution-one-for-all.md`, `ofa-repos.md`, `working-style-jarvis.md`. Sibling folders in that project dir are session transcripts (two UUID folders). |
| User-level `C:\Users\jaiva\.claude\` | outside repos | `settings.json` and a `skills/` folder exist; no `agents/`, `commands/`, `hooks/` or `CLAUDE.md`. Not opened. |
| local-voice-assistant | — | No agent or instruction files. Its README is the only documentation. |

---

## 10. E-Brain integration touchpoints

| # | Touchpoint | Path | What is there now | Natural insertion point |
|---|---|---|---|---|
| 1 | **e-brain placeholder component** | `existing:one-for-all-web/src/features/e-brain/components/e-brain.tsx` | `export function EBrain() { return null; }` with a comment saying it is blank by intent | L3-5 (body). The spec (B4.3) currently requires it to stay blank, so changing it is a spec decision. |
| 2 | e-brain barrel | `existing:one-for-all-web/src/features/e-brain/index.ts` | `export { EBrain } …` | L1 (add exports here; routes import only the barrel) |
| 3 | e-brain route | `existing:one-for-all-web/src/app/e-brain/page.tsx` | Renders `<EBrain/>`; no metadata | L1-2 (add `import type { Metadata }` and `export const metadata = { title: … }` like `existing:one-for-all-web/src/app/history/page.tsx` L1-3) |
| 4 | **Nav config** | `existing:one-for-all-web/src/components/layout/shell.tsx` | `nav` array; the e-brain item uses `image: "/media/e-brain.png"` | L74-79 (item), L156-172 (`NavIcon` special cases; e.g. a status badge like Watchers L377-405), L556-575 (breadcrumb map for sub-routes such as `/e-brain/...`) |
| 5 | e-brain icon asset | `existing:one-for-all-web/public/media/e-brain.png` | 236x236 PNG | Replace in place, or add siblings under `existing:one-for-all-web/public/media` |
| 6 | **App-wide state** | `existing:one-for-all-web/src/app/providers/app-provider.tsx` | Single `useApp` context. Reset broadcasts `ofa:reset-local-preview`. | `AppContext` type L44-74; state block before L373; value object L375-405; `reset()` L363-372 (clear E-Brain preview state on "Reset local demo"). Or a sibling provider next to it, nested in `existing:one-for-all-web/src/app/layout.tsx` L36-42. |
| 7 | **Arc Reactor** | `existing:one-for-all-web/src/features/arc-reactor/components/arc-reactor.tsx` | Engine status, GO PRO routing between R1 and R2 | Routing rules L14-35, state L69-76; controller `existing:one-for-all-web/src/lib/reactor/reactor-transition.ts` L48-107 |
| 8 | **Playground Agents registry** | `existing:one-for-all-web/src/features/playground/components/playground.tsx` | In-memory `Agent[]` (name, `.md` file name + body, trigger phrases) | Type L29-36, samples L38-57, state L76-81, save L95-130, tab panel L212-436. Because of the cross-feature rule, sharing it with e-brain means moving the type and data to `src/lib/` (or a provider) first. |
| 9 | Trigger-phrase consumer (Home) | `existing:one-for-all-web/src/features/home/components/assistant.tsx` | `submit()` → `interruptionPreview` → `classifyPreview` → `start` | L58-76 (the only place typed or "spoken" text is routed; nothing matches agent triggers) |
| 10 | Text classifiers | `existing:one-for-all-web/src/lib/demo.ts` | `classifyPreview`, `interruptionPreview` (Hinglish words such as `ruk`, `mat`, `nakli`) | L414-436 |
| 11 | **History** | `existing:one-for-all-web/src/features/history/components/history-calendar.tsx` | Calendar over static `historyRows` | Data source L10 and L279-286; rows `existing:one-for-all-web/src/lib/demo.ts` L452-523; detail `existing:one-for-all-web/src/components/tasks/task-detail.tsx` L27-60 |
| 12 | **Watchers** | `existing:one-for-all-web/src/features/watcher/components/watchers.tsx` | Local watcher list + notices sent into AppProvider | Type L22-28, list L31-34, notice emit L206-212; notices app-provider L275-311 |
| 13 | Settings "Profile & facts" (spec Memory = profile facts) | `existing:one-for-all-web/src/features/settings/components/settings.tsx` | Fictional facts saved to localStorage `one-for-all-preview-preferences` | Tabs L13-19 and L90-96; facts form L102-148; save L54-73 |
| 14 | **Shared types** | `existing:one-for-all-web/src/lib/demo.ts` | Role, Task, TaskStatus, OrbState, Draft, … | After L241 (TaskAction), or a new `src/lib/<name>.ts` that must be imported (no-orphans) |
| 15 | **Backend contract registry** | `existing:one-for-all-web/src/lib/integrations.ts` | 30 proposed features; `integrate(id)` throws for unknown ids | Append a `feature({...})` before `];` at L1249; must satisfy `existing:one-for-all-web/tests/domain.spec.ts` L67-81 (`/v1/` path or local-adapter). Then `npm run docs:generate`, which updates `existing:one-for-all-web/scripts/generate-handoff.ts` outputs; the screen-to-feature map is in its L5 template. |
| 16 | Adapter seam precedent | `existing:one-for-all-web/src/lib/dictation/contracts.ts` | `DictationServices` interface + mock implementation | L82-118 (pattern to copy for a memory/brain client) |
| 17 | API/fetch client | — (none exists) | No fetch, WebSocket or route handlers. The no-network test is `existing:one-for-all-web/tests/journeys.spec.ts` L210-228. | A new `src/lib/` client and/or `src/app/**/route.ts` (route files are exempt from no-orphans) |
| 18 | Env example | `existing:one-for-all-web/.env.example` | One tooling var; "The app reads no environment variables" | After L3. Also update the README Environment section L56-58. |
| 19 | Architecture rules | `existing:one-for-all-web/.dependency-cruiser.cjs` | 4 rules | L11-50 (`forbidden`) |
| 20 | Test dirs | `existing:one-for-all-web/tests` | 15 flat specs | New `tests/e-brain.spec.ts`; add `/e-brain` to the route lists in `existing:one-for-all-web/tests/quality.spec.ts` L4-23 and L62-75 only once the page has a `main h1` |
| 21 | Playwright config | `existing:one-for-all-web/playwright.config.ts` | Port 3100, seeded storage | L15-26 (seed any E-Brain storage), L32-37 (webServer) |
| 22 | README structure | `existing:one-for-all-web/README.md` | `e-brain/ Reserved placeholder (renders nothing on purpose)` | L72 and L62-89 |
| 23 | Spec | `existing:one-for-all-web/docs/SPEC_ITERATION_1.md` | B4.3 says e-brain is blank; B7.1 Memory in core; B8 tables | L281-296, L524, L647-653 |
| 24 | Agent instruction file | `existing:one-for-all-web/AGENTS.md` | Next block only (re-added by `next dev`) | After L9 (outside the BEGIN/END markers) |
| 25 | Claude settings | `existing:one-for-all-web/.claude/settings.json` | Attribution only | Top-level object L1-6 (hooks, permissions, etc.) |
| 26 | CI workflows | — (none) | No `.github/` in any repo | `one-for-all-web/.github/workflows/` (new) |
| 27 | **Python service location** | `existing:one-for-all-api` | README only | `existing:one-for-all-api/README.md` L1-3 (the whole repo is empty) |
| 28 | Voice prototype memory | `existing:local-voice-assistant/src/llm.py` | In-memory 10-message history | L62 (history), L141-164 (`generate`) |

---

## 11. CI and deploy

- **No CI** anywhere: no `.github/` folder (so no workflows, no dependabot) in one-for-all-web, one-for-all-api or local-voice-assistant.
- **No Vercel config** (`vercel.json` absent). README "Deploy" (L97-105) says the site deploys to Vercel with the default Next.js preset: build `npm run build`, output `.next`, repo root, no env vars. Whether a Vercel project is actually linked could not be checked; there is no `.vercel/` folder.
- **No Docker** (no Dockerfile or compose) in any repo.
- The only "pipeline" is the local `npm run verify`.

---

## 12. Git state (read-only commands)

### one-for-all-web
- Current branch `main`, "up to date with 'origin/main'", working tree clean, no stashes. Remote `origin https://github.com/OFA-Labs/one-for-all-web.git`.
- Branches:
  - `main` 94eb271 (tracks origin/main)
  - `staging` 94eb271 (tracks origin/staging)
  - `chore/repo-restructure` 9f9f706 (local only, already merged)
  - remotes: `origin/main`, `origin/staging`, `origin/HEAD -> origin/main`
- Last commits (all by jv-singh, 2026-11-22 / 23):
  ```text
  94eb271 docs: add final iteration-1 product spec          (2026-11-23 06:07 +0530)
  6469961 chore: merge repo restructure
  9f9f706 chore: add dependency-cruiser architecture guard
  8210563 chore: root hygiene for publishing
  30feca5 refactor: restructure src into app/features/components/lib layout
  dc6823b chore: drop unused @radix-ui/react-* direct dependencies
  e5e11c5 refactor: remove unused exports
  2bc2703 chore: remove unreferenced public media
  3ab5215 chore: remove unused Badge primitive
  02eb54e chore: remove unreferenced captured command logs
  (11th, root: 902b3c0 chore: initial import of ONE FOR ALL web frontend)
  ```

### one-for-all-api
- Branch `main`, up to date with origin/main, clean. Branches `main` and `staging` (both 6723480, tracking their remotes).
- Only commit: `6723480 chore: initial commit` (2026-11-22 21:59 +0530, jv-singh). Remote `https://github.com/OFA-Labs/one-for-all-api.git`.

### local-voice-assistant
- Not a git repository (`fatal: not a git repository`).

---

## 13. Unknowns and discrepancies

1. **Backend naming**: the spec says `one-for-all-core` (FastAPI) and two repos (`SPEC_ITERATION_1.md` L531, D5 L903). GitHub has `one-for-all-api` (empty) and no core repo. Which name is canonical is not recorded anywhere in code.
2. **Extension folder**: the spec says the extension lives in `one-for-all-web/extension/` (B7.1, D5). That folder does not exist; only the `/extension` preview page does.
3. **Why `dictation-hotkey.spec.ts:95` fails**: only the failure artifact was read (expected "Page unfocused", got "Caps Lock detected · 1 press."). The cause (focus/visibility detection versus test timing in headless Chromium) was not investigated, because running tests is out of scope.
4. **Vercel linkage and live URL**: README claims Vercel deploys, but there is no config or `.vercel/` folder. Whether a project or domain exists is unknown.
5. **Push status vs memory**: the memory index says the repos are "not yet pushed", but git shows `main` and `staging` up to date with origin, and GitHub `pushedAt` is 2026-11-23T01:09Z. The memory note is likely stale; the contents of `ofa-repos.md` were not opened, by instruction.
6. **Naming drift**: the spec says "Arc Reactor" and "Arc R1"; the UI says "OFA Engine" and "R1/R2". The nav declares `/media/arc-reactor.png` but never renders it (shell.tsx L72 vs L158-159). The spec says the Arc Reactor shows the hero orb video; the code uses `ofa-engine-heart.mp4`.
7. **Stale paths in dated docs and agent outputs**: `docs/dictation/ARCHITECTURE_NOTES.md` cites `src/components/provider.tsx`, and `.promptible/research-brief.md` cites `src/components/arc-reactor.tsx`. Both are pre-restructure and do not exist now. `render-brief.json` points to `voice-agents\.agents\skills\…` (absent). `local-voice-assistant/.venv` was created from `voice-agents\.previous-media-venv` (absent), but its `home` Python 3.12 install exists, so the venv probably still works (not executed).
8. **Media sources**: `scripts/process-video.py` and `scripts/home-coast-video.py` read source videos from the workspace root (`Screen Recording 2026-11-15 160400.mp4`, `TheSnapInsta.to_instagram_720p_hd.mp4`). Neither exists there now, so the scripts cannot be re-run as-is.
9. **Not inspected by design**: `.env*` secrets (none found besides `.env.example`), `.claude/settings.local.json` (absent), user-level `~/.claude/settings.json`, memory file contents, the `ebrain-tournament/` folder (including `.orchestrator/sealed`), `.next/`, and the binary media.
10. **Runtime behaviour** (visual rendering, timings, whether `npm run verify` passes apart from the known failure) was not observed, because no dev server, build or test was run. Statements about behaviour come from reading code and the last-run artifacts only.
