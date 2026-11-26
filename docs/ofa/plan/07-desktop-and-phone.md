# 07 — Desktop Harness and Phone Surface
**Purpose:** §10 decisions with evidence · **Depends on:** §9, §10, 04 · **Files likely touched:** `api/ofa/harness/{api,uia,ocr,vision,adapters/*}.py`, `api/ofa_execution/windows.py` · **Done when:** M05 rows H1–H8 pass; phone decision recorded (this file).

## Detected OS: Windows 11 (10.0.26300). Only the Windows backend is built. macOS/Linux backends: interface stubs raising `UNSUPPORTED_OS` + doc line; not tested.

## Helper API (`ofa/harness/api.py`) — identical semantics on every backend
| Helper | Returns / does |
|---|---|
| `open_app(name)` | resolve via installed-app discovery (Start Menu, App Paths, `Get-StartApps`/AppsFolder, running processes) → launch → wait for window; multiple matches → `AMBIGUOUS(options)` |
| `screenshot(window=None)` | `RawImage` (local only); `redact()` → `RedactedImage` |
| `screen(window=None)` | `[Element{id, text, role, bbox, source: "uia"|"ocr"|"vision", enabled, is_password}]` |
| `find_text(q, role=None)` | best element by exact → normalized → fuzzy (rapidfuzz ≥ 88); never returns near match as exact (`match: exact|fuzzy`) |
| `click_text(q)` / `click(element_id)` | UIA Invoke/SelectionItem → else SendInput mouse at bbox center |
| `type_text(text, element_id=None)` | UIA ValuePattern.SetValue (replace) or SendInput Unicode (insert at caret) |
| `key(combo)`, `scroll(dir, amount)`, `wait_for_text(q, timeout)` | SendInput; poll screen() |
Every helper is invoked only via `ofa_execution` Hand → Gate (no direct path, §10.1). Effects of `click`/`key` are tier-classified by 04 using the element label.

## Backends (priority order)
1. **UIA** (comtypes, existing `windows.py`) — exact; tree walk bounded (depth 25, 2,000 nodes, 1.5 s).
2. **Windows OCR** (`winrt Windows.Media.Ocr`, local, languages en + hi if installed) — text + bbox for canvas/Electron gaps.
3. **Vision model** — only if the selected engine `supports_vision` and user enabled it; screenshot redacted first. With gpt-oss default: unavailable → step reported `BLOCKED_NO_VISION`.
Browsers: prefer paired browse adapter / CDP (DOM, exact URLs) over UIA (§9 order).

## Adapters
`ofa/harness/adapters/<app>@<n>.yaml`: selectors/hints (e.g. search box role+name, compose field) for WhatsApp, Slack, VS Code, Cursor, Chrome/Edge, Gmail, GitHub. Versioned, no personal data, no demo flows. Generic path must work without them (13: at least one app with no adapter, e.g. Notepad++ or Settings).

## Documented limits
OCR sees text, not icons · DRM video renders black · secure desktop/UAC prompts and secure-input fields cannot be automated (handoff) · elevated windows reject input from a non-elevated OFA (UIPI) → handoff · Electron apps may expose sparse UIA (OCR fallback).

## Phone Harness evaluation (time-boxed; fetched 2026-11-26)
| Item | Evidence |
|---|---|
| License | **MIT**, © 2026 shawn pana — github.com/phone-harness/phone-harness/blob/main/LICENSE |
| Version | no releases tagged; PyPI latest unspecified; main ≈150 commits → M10 must pin a commit SHA |
| Language / backends | Python ≥3.10; iPhone via macOS iPhone Mirroring (macOS 15+), Android via adb (Win/mac/Linux), paid Cloud |
| Helpers (from README/install.md) | ensure_device, open_app, tap, tap_text, find_text, type_text, screen, screenshot, wake |
| Text source | iPhone: Apple Vision OCR; Android: uiautomator accessibility tree + adb screenshots |
| Network | usage **telemetry on by default** (disable: `DO_NOT_TRACK=1` / `PHONE_HARNESS_TELEMETRY=0`), daily PyPI update check (`PHONE_HARNESS_NO_UPDATE_CHECK=1`), Cloud → api.phone-harness.com |
| Install | no pipe-to-shell; `uv tool install`; README "setup prompt" instructs an agent to install + read onboarding.md → **not run** |
| `helpers.py` | NOT read: root path 404; real path `src/phone_harness/helpers.py` → read at pinned SHA in M10 step 1 |
| Stealth / real numbers | Cloud-product features → **forbidden** (§8.7) |

**Decision: Option 2 now (adapt the design), Option 1 later as optional M10 (Android/adb only).**
- Option 2: the helper vocabulary and "one API, many backends" design is reimplemented in `ofa/harness` from scratch; no code copied, so no notice needed. If M10 copies any code, keep the MIT notice in `api/THIRD_PARTY.md`.
- Option 1: host is Windows → iPhone Mirroring impossible; Android over adb is the only local path. Install in an isolated venv with telemetry + update check disabled, local backend only, no Cloud/MCP. Phone Tier-2 actions go through the same Gate. Never blocks acceptance.
- Option 3 rejected: the design is useful and the license permits reuse.
