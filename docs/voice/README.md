# OFA Voice - Iteration 1

Updated **2026-11-26 (Asia/Calcutta)**. Single consolidated context, setup, capability and acceptance record.
This replaces the earlier master/planning/prompt/status/checklist/build reports. The implementation in the
feature repositories is authoritative; do not copy obsolete proposal code over it.

## Completion statement

The **scoped iteration-1 backend path is implemented end to end**:
**physical activation -> microphone -> STT -> local command/action -> verified result -> TTS acknowledgement**.
The original user confirmed real WhatsApp launch plus audible acknowledgement on 2026-11-25.
This is speech-to-action-to-speech; general LLM conversation, a universal OS agent and production release
are **not 100% complete**. Major computer-control cases are implemented, while many broader cases,
edge conditions and acceptance gates remain below. The updated physical voice/file trial and real Slack
sending were explicitly deferred by the user. Do not mark them passed.

## Architecture and decisions

- **Python native Windows companion + FastAPI**, with the existing React/Next web interface. No Electron.
- Web connects directly to authenticated loopback on the user's computer, never to a cloud server's localhost.
- Native Caps Lock hook and blue orb work independently of the focused website. Windows mic access is
  required; this native capture mode does not need a browser getUserMedia grant.
- Deepgram primary STT/TTS; Gradium fallback. English and Hindi Deepgram TTS and both STT providers
  passed real service probes using synthesized speech. Gradium Hindi parity is unavailable.
- HassIL operation grammar, discovered app identities, aliases and safe fuzzy suggestions handle routine
  OS/site/window/file/send actions with **zero LLM calls**. There is no app-by-app phrase execution script.
- Existing serial Engine/Gate is reused: typed plans, scoped hands, fresh readback, exact-action approval,
  one-use authority and honest unknown outcomes. No second planner/executor or raw model shell commands.
- Native UIA/SendInput and paired browse foundation remain available for scoped structural automation;
  arbitrary semantic UI control is not exposed as a universal voice capability.
- Browser nonextractable P-256 key, native origin/key approval, DPAPI settings, short-lived sessions and
  one-use WebSocket tickets retain pairing. Native folder/window permission upgrades stay separate.
- LocalDevelopmentSessionPort is explicitly development identity. Production account sign-in is user-owned;
  the preview role picker is not authentication. Future sign-out must integrate trusted revocation.
- Speaker mode gates capture during speech. Headphone mode enables interruption; full acoustic echo
  cancellation is not implemented. Metadata logs exclude raw audio, transcripts, file bodies and secrets.
- Default/named-browser receipts prove dispatch only. Paired browse can independently verify tab URLs;
  no personal profile is silently paired. Uncertain Slack completion is never retried automatically.

## Workspace, branches and reproduction

| Item | Value |
| --- | --- |
| API worktree | `.worktrees/voice-pipeline-api`, branch `feat/voice-pipeline`, staging baseline `1846674` |
| Web worktree | `.worktrees/voice-pipeline-web`, branch `feat/voice-pipeline`, staging baseline `1d54fb5` |
| Publication | `jvsing` forks -> `OFA-Labs/one-for-all-api:staging` and `OFA-Labs/one-for-all-web:staging` |
| Development website | `http://127.0.0.1:3000` |
| Native API | `http://127.0.0.1:8767`, loopback only |
| Current companion | 0.2.2, unsigned Windows development build |

Original `one-for-all-api/` and `one-for-all-web/` shared-checkout edits are unrelated EBrain work and stay untouched.
Staging/production are not deployed; their exact origins remain environment-configurable and empty.
This report consolidation does not change executable behavior or the installed speech provider credentials.

From the API feature checkout (Windows, Python 3.12):

```powershell
./scripts/setup_voice.ps1
# Set DEEPGRAM_API_KEY and GRADIUM_API_KEY locally; never paste their values into Git/PRs.
./.venv-voice/Scripts/python.exe -m voice --live --env-file C:/path/to/private/.env
# Optional: protect the two speech credentials for this Windows user, without printing them.
./.venv-voice/Scripts/python.exe -m voice --env-file C:/path/to/private/.env --save-speech-credentials --configure-only
```

From the matching web checkout (Node 24 used locally):

```powershell
npm ci
npm run dev -- --port 3000
```

Open `/desktop`, connect once and approve the native origin/key dialog. Keep OFA available for status,
switch to another ordinary website, press Caps Lock and speak. Stop/idle retains pairing; Disconnect
revokes grants and permission upgrades. Reload/restart never resumes recording or replays a command.
Alt+Shift+J and web Stop are additional controls. Quit retains saved pairing.

| Local configuration | Meaning |
| --- | --- |
| `DEEPGRAM_API_KEY`, `GRADIUM_API_KEY` | Runtime speech credentials, outside Git and browser bundles |
| `OFA_DEV_ORIGIN` | Verified local origin above; change only to the actual frontend origin |
| `OFA_STAGING_ORIGIN`, `OFA_PRODUCTION_ORIGIN` | Empty until real deployments; never wildcard origins |
| `NEXT_PUBLIC_OFA_COMPANION_URL` | Public loopback URL only; never a provider secret |
| `NEXT_PUBLIC_OFA_COMPANION_DOWNLOAD_URL` | Empty until a real installer URL exists |
| `OFA_SLACK_BOT_TOKEN`, `OFA_SLACK_CHANNEL_IDS`, `OFA_SLACK_TEAM_ID` | Optional local token, permitted C/G channel IDs, expected workspace; live send deferred |
| `OFA_BROWSE_BINARY`, `OFA_BROWSER_ORIGINS` | Optional reviewed browse executable and exact destination origins after native extension pairing |
| `VOICE_HEADPHONES`, `VOICE_LANGUAGE` | Headphone/gated speaker and language preferences; see `.env.voice.example` |

Slack needs files:write/files:read and channel membership. Its adapter checks auth.test workspace identity,
uploads exact approved bytes through the supported external upload protocol, then checks files.info.
No token or real channel is needed for local HTTP protocol tests.

## Packaging and validation commands

```powershell
./.venv-voice/Scripts/python.exe -m pytest tests/voice tests/local_execution tests/test_api.py tests/test_cors.py tests/test_store.py -q
./.venv-voice/Scripts/python.exe -m voice --fake-demo
./.venv-voice/Scripts/python.exe -m pip check
./scripts/build_voice.ps1
# Extract the entire development ZIP; quit the old companion before updating.
./dist/install_voice.ps1
```

Owned interactive Win32 close tests need `OFA_INTERACTIVE_TESTS=1`; stop the companion first so the fixture
can register Alt+Shift+J. Real browse integration is separately opt-in; the repo's browser smoke script uses
a disposable profile and reviewed pinned browse/extension. Do not silently pair a personal browser.

Web checks: `npm run typecheck`, `npm run lint`, `npm run check:arch`, `npm run build`, and
`npx playwright test tests/desktop-voice.spec.ts`. Full web test failures must remain visible.

The installer stages a per-user update, preserves pairing/settings and retains the previous build for rollback.
Startup is opt-in. `%LOCALAPPDATA%/OFA/uninstall_voice.ps1 -WhatIf` previews removal;
`-RemoveSavedData` explicitly removes protected settings too. No administrator default is required.

## 1. What changed in this iteration

- [x] Canonicalize duplicate executable/shortcut/Store entries. Slack, Notepad, Excel and OneNote now resolve uniquely.
- [x] Preserve distinct Photos products: `Windows Photos` and `OneDrive Photos`. Bare `Photos` asks for a choice.
- [x] Discover and launch **Claude Code** separately from Claude desktop, using the installed native CLI and Windows Terminal.
- [x] Verify Claude Code using its process path/start time, owning terminal process and unique visible window title. No prompt is sent.
- [x] Strengthen the shared name/binary policy for shells, interpreters, security/system tools, installers and internal helper programs.
- [x] Connect window focus/minimize/maximize/restore to the live voice dispatcher.
- [x] Add safe window close with fresh approval. Unsaved-work dialogs stay open for human assistance; no force-kill/discard.
- [x] Connect bounded file read, exact-text write and saving the previously selected text to the existing FileHand/Gate.
- [x] Add native read/write folder selection, persisted permission upgrades, app refresh and native manual app registration.
- [x] Preserve case-sensitive URL paths/query values and exact supplied file text. Recognize spoken `dot` domains/filenames.
- [x] Connect mixed app/site/search sequences and named Chrome/Edge URL dispatch without an LLM.
- [x] Connect real executor approval, question, handoff, completion and failure events to the voice host and web panel.
- [x] Add bound approval/rejection buttons and conservative spoken decisions. Unclear speech never approves.
- [x] Stop cancels pending work, including while approval is open. Changed state invalidates an old approval.
- [x] Implement the real Slack external-upload protocol, workspace identity check, channel scope, immutable bytes and delivery readback.
- [x] Test Slack locally, including a lost completion reply without retrying the send. **No real Slack file was sent.**
- [x] Add output-callback first-sample/silence telemetry and output-device failure handling; mark callback timing as an estimate.
- [x] Run a 30-minute synthetic STT replay/task/memory soak: **62,069 cycles passed**. This is not a live microphone soak.
- [x] Add live-host single-instance protection, explicit startup preference, Quit, staged updates/rollback backup and uninstall script.
- [x] Keep sign-in and live OFA Engine reasoning deferred as instructed. All routine adapters have no LLM provider.

## 2. Applications you can open

Use `Open`, `Launch`, `Start` or `Bring up` followed by an indexed name. Exact matches execute;
fuzzy matches suggest rather than guessing. An installed app must pass policy and produce process/window evidence.

| Target / command | Current evidence | Qualification |
| --- | --- | --- |
| `Open WhatsApp` / `WhatsApp kholo` | Human physical voice M0 passed, with spoken acknowledgement | Original source-run milestone; final-build physical rerun is separate |
| `Open VS Code` / `Open Visual Studio Code` | Real native Engine/Gate process/window readback passed | Complete physical voice rerun not recorded |
| `Open Claude Code` | Real native CLI + owned terminal/window verification passed | Separate from Claude desktop; no prompt submitted; requires native claude.exe and wt.exe |
| `Open Slack` | Real native launch/readback passed after canonicalization | Slack workspace login and file sending are separate capabilities |
| `Open Notepad` | Real native launch/readback passed | Duplicate Store/exe entries resolved |
| `Open Excel` | Real native launch/readback passed | Duplicate shortcut/exe entries resolved |
| `Open OneNote` | Real native launch/readback passed | Duplicate entries resolved |
| `Open Windows Photos` | Real native launch/readback passed | Different product from OneDrive Photos |
| `Open Calculator` | Real native launch/readback passed | Physical voice trial not recorded |
| `Open Chrome` | Real native launch/readback passed | Does not mean arbitrary existing tabs are controlled |
| `Open Microsoft Edge` | Real native launch/readback passed | Does not certify hosted loopback permission behavior |
| `Open Claude` / `Open Claude desktop` | Discovered eligible Store app | Native launch/physical voice acceptance not separately recorded |
| `Open ChatGPT`, Paint, Cursor, Obsidian, Word, PowerPoint, Teams, Outlook, Zoom Workplace | See current catalog below | Indexed availability is not certification of each app's launch/voice behavior |
| `Open Photos` | Local clarification; qualified app names offered | Two genuinely different installed products; no silent choice |
| Spotify / Discord / Telegram | Not confirmed in this machine's index | Install, refresh or register an eligible installed executable before testing |

The expandable inventory at the end is generated from current discovery. Newly installed apps can be
refreshed without editing a per-application command script. Some apps may still need an alias or a
supported launch mechanism. Portable executables can be selected through **Register installed app**.

## 3. Websites and compound requests

| Command | Implemented behavior | Evidence / limit |
| --- | --- | --- |
| `Open GitHub`, `Open github.com`, `Open YouTube` | Validated public HTTP/HTTPS URL -> default browser | Real OS dispatch; page loading/login not asserted |
| `Open example dot com` | Spoken domain normalization | Local routing tests; public DNS/IP validation still applies |
| `Open https://example.com/MyReport.pdf?Key=AbC` | Preserve path/query case | Regression passed; no URL lowercasing |
| `Search for Cats and Dogs on Google` | Encoded query; preserve query words/case | Routing tested; no LLM |
| `Open Chrome and navigate to ChatGPT` | Open trusted Chrome, dispatch the resolved URL to that browser | Real combined dispatcher/OS test passed; page load not verified |
| `Open GitHub and open YouTube` | Execute both actions serially through the existing Engine | Real combined dispatcher/OS test passed; zero LLM calls |
| `Navigate to github.com` | Browser dispatch by default | With locally configured/paired browse and exact destination permissions, uses existing BrowserHand for URL readback |
| `Open my repository/dashboard` | Requires an explicit saved URL binding | No guess from account data, foreground tab or model; use full URL until bound |
| Control an arbitrary existing personal Chrome tab | Optional paired browse extension/adapter required | Default app/URL launching does not grant existing-tab DOM access |

Default/named-browser dispatch is deliberately acknowledged as sending the link, not as a successful
page load. The existing browse adapter was independently tested in an **owned disposable Chromium
profile**, including real page mutation approval and readback. A user's personal profile is not silently paired.

## 4. Commands beyond opening

| Capability | Current implementation | Permission / behavior |
| --- | --- | --- |
| `Focus VS Code`, `Minimize Notepad`, `Maximize Excel`, `Restore Excel` | Live handlers connected; real owned Win32 window tests passed | First enable **Window controls** in Desktop Integration and approve the native dialog |
| `Close Notepad` | Live safe-close handler; real normal and unsaved-work fixtures passed | Fresh exact-window approval; ambiguous windows fail closed; save prompts require the user |
| `Read Notes dot md` | Live scoped file read; real FileHand/Engine integration tested | Choose read/write folder natively; first 1,000 characters spoken, first 16,384 previewed |
| `Write Hello and Goodbye to Notes dot md` | Exact supplied text, no generation | Choose write folder; approve exact text/path/version before atomic write/readback |
| `Write "Title\nExact Text" to Notes.md` | Exact quoted text and supported escapes preserved | Supported text extensions: .md, .txt, .csv, .json |
| `Save Copy.md` after reading/writing selected text | Reuses the bound text; never invents a document | Missing bound text produces clarification; each write still needs approval |
| `Send Notes.md to C123ABC456` / `Send this markdown file to Slack` | Real Slack connector implemented; local protocol tests passed | Requires local bot token, allowlisted channel and native-selected readable file; every send needs approval |
| `Send this markdown file` after a file changes | Rejected until selection/read is refreshed | Exact approved artifact/hash and workspace/channel binding |
| Caps Lock / Alt+Shift+J / web Stop / spoken Stop | Cancels pending voice/executor work and releases devices | Stop retains pairing; explicit Disconnect revokes grants and folder/window upgrades |
| Startup / Quit / refresh / manual registration | Web controls connected to narrow authenticated companion operations | Native confirmation for OS preferences; no automatic startup opt-in |
| Type/click/scroll arbitrary controls by voice | **Not exposed as arbitrary voice commands** | Foundation hands exist; arbitrary content/semantic targeting would exceed the current bounded command pack |
| Send WhatsApp messages | **Not implemented** | M0 authorizes opening WhatsApp; it does not implement or authorize message delivery |
| Review PR / write a newly reasoned specification | **Deferred** | OFA Engine/LLM integration explicitly excluded by the user in this iteration |

Files are bounded UTF-8 text: reads/sends at most **64 KiB**, write contract at most **16,384 characters**
and 64 KiB encoded. No arbitrary browser-supplied paths or shell commands reach execution. File selection
and exact action content are independent of any model. Selection persists in memory until Disconnect/process exit;
permissions persist under current-user DPAPI. The latest read/write text preview is shown only while connected.
Authentication/validation errors include CORS headers only for configured origins, so Chrome/Edge can read the correct denial instead of a false network-offline error.

## 5. Setup once, then use

- [x] Python companion runs in the user's Windows session; browser is the interface, not the OS executor.
- [x] Verified local origin: `http://127.0.0.1:3000`; companion binds only `127.0.0.1:8767`.
- [x] Hosted origins remain empty/configurable. No fabricated domains or wildcard CORS.
- [x] Native origin/key consent, browser nonextractable P-256 key, one-use challenges and WS tickets.
- [x] Reload/restart reuses the saved grant after fresh key proof; never restores an armed mic or replays work.
- [x] Physical Caps activation works independently of the focused website. Native capture needs Windows mic access, not browser getUserMedia.
- [x] Permission upgrades are explicit and native. Existing launch consent is not silently expanded to files/window mutation.
- [x] Approval binds task, exact action, current read hash, epoch and expiry; stale/replayed decisions are rejected.
- [x] Metadata logs omit transcripts, file contents, keys, raw audio and approval bodies.
- [x] DPAPI speech settings remain separate from pairing and outside the distributed bundle.
- [ ] Real account sign-in/session authority: user-owned external dependency. Local-development identity is not production authentication.

The UI offers **Connect computer**, **Enable window controls**, native folder selection, app inventory/refresh,
manual registration, exact-action cards, human handoff, startup preference, **Stop voice**, **Quit companion**,
and **Disconnect computer**. Setup is reused until Disconnect/sign-out. Real sign-out still needs the trusted
account adapter; the preview role selector is not an authentication signal.

## 6. Full checkpoint ledger

| Checkpoint | Implementation status | Acceptance still outstanding and why |
| --- | --- | --- |
| CP-0 discovery/baseline/provider checks | Implemented; real providers and selected installed apps probed | Independent clean-machine timing and human language ratings need another environment/listeners |
| CP-1 configuration/contracts/fakes | Implemented and locally tested | Remote CI must be checked on the published PR; local checks do not certify CI |
| CP-2 language/intent/catalog | Implemented; generic names, safe fuzzy suggestions, duplicate choices, exact URLs/text | Not every pronunciation/app name has a physical voice trial |
| CP-3 capture/Caps/orb | Implemented; real M0 | Device unplug/conflicts/acoustic behavior across hardware not certified |
| CP-4 speech to verified WhatsApp | **M0 PASSED** | Updated installed-build physical rerun is not a substitute for or inferred from source-run M0 |
| CP-5 Engine boundary/chunking contract | Current contract implemented; **live reasoning deferred** | User excluded live Engine/LLM; no PR-review/spec-generation completion claim |
| CP-6 TTS/playback/cache | Implemented, real provider probes, callback tests and output loss handling | Real listener quality and acoustic first-sample/barge-in targets require physical measurements |
| CP-7 Gradium/failover/breakers | Implemented and fault-tested locally; both providers probed | Forced live failure/priority-switch hardware trials remain; Gradium Hindi parity is unavailable |
| CP-8 routine capability dispatch | App/window/file/site/browser/send handlers implemented and connected | Slack live delivery deferred; personal browser pairing/saved resource bindings depend on actual user resources |
| CP-9 approvals/progress/handoff | Real executor wired to UI and conservative voice decisions | Automated exact-file/Stop/state-change tests and Win32 close passed; human speech approval trial remains |
| CP-10 metadata/latency | Implemented, callback metadata added, report CLI available | Callback timestamps are estimates; no invented physical p50/p95 or 50-run language/device results |
| CP-11 transport/UI/hardening | Local pairing/UI/permission/cancellation tests implemented; 30-minute synthetic soak passed | Public HTTPS Chrome/Edge allow/deny needs actual deployed origin; full live audio soak/fault matrix remains |
| CP-12 host/bootstrap/package | Local unsigned bundle/install flow; single instance/startup/quit/update/uninstall implemented | Trusted signing/download hosting, independent Windows install timing and remote CI are external acceptance gates |

## 7. Acceptance-criterion ledger

| Criterion | Recorded status |
| --- | --- |
| AC-01 clean setup within 10 minutes | Not certified: no independent fresh Windows machine/VM and timed human installer trial |
| AC-02 general reasoning response | Deferred intentionally to OFA Engine |
| AC-03 Hindi speech | Real Deepgram Hindi TTS probe passed; full human Hindi interaction/fallback acceptance remains partial |
| AC-04 Hinglish pronunciation/display | Policies/local tests; human listener ratings not performed |
| AC-05 real WhatsApp opening | Human M0 passed |
| AC-06 Claude Code with another browser focused | Native Code process/terminal/window launch passed; physical cross-browser voice trial not recorded |
| AC-07 headphone interruption | Callback cancellation/silence tests passed; physical loopback timing not measured |
| AC-08 STT replay/failover | Local fault/replay tests and separate real provider probes passed; live mid-utterance failure trial outstanding |
| AC-09 partial/dual speech failure | Local fault tests passed; real forced network/audio failure matrix outstanding |
| AC-10 approval workflow | Real gate/UI/voice wiring, exact-file/changed-state/Stop tests; human spoken decision acceptance outstanding |
| AC-11 honest blocked feedback | Fixed local messages and actual executor errors; broad multilingual human acceptance incomplete |
| AC-12 security/privacy | Auth/origin/key/replay/Stop/catalog/file/connector checks; not an independent security audit |
| AC-13 real latency distributions | Not certified: no physical 50-run per-language/device/network dataset |
| AC-14 secret-free Windows CI | Workflow/local checks exist; PR publication is authorized now; see the PR for actual remote CI status |
| AC-15 reversed provider order | Configuration/fake tests; real reversed-priority voice acceptance not recorded |
| AC-16 zero LLM routine actions | Implemented in connected app/window/file/site/send adapters; mixed OS dispatch observed with zero calls |
| AC-17 catalog/ambiguity | Canonical identities, qualified real products, local choices and native registration implemented/tested |
| AC-18 mixed review/save/send | Routine file/send pieces implemented locally; reasoning remains explicitly deferred; no real mixed review workflow claim |
| AC-19 reusable pairing | Automated persistence/proof/revocation checks; final installed same-profile human lifecycle rerun remains unreported |
| AC-20 sign-out/principal/revocation | Device/local contracts tested; production sign-out requires user-owned trusted identity adapter |
| AC-21 hosted HTTPS Chrome/Edge | Cannot run until staging/production exists; none supplied/deployed |
| AC-22 website/search/named navigation | URL-case/query tests, real named/mixed OS dispatch; optional real browse fixture passed; personal profile/public page success not inferred |

## 8. Test evidence and remaining blockers

Final local API/execution run: **140 passed, 1 skipped**; the separate real browse smoke passed.
Dedicated desktop web tests: **3 passed**. Full web run: **135 passed, 1 existing dictation-focus failure**, previously reproduced on untouched staging. A preceding intermittent unchanged EBrain WAL-lock test failure passed focused retry and the complete rerun.
Build/typecheck/lint/architecture, frozen fake smoke and all 50 bundled-module source comparisons passed.
Current unsigned development bundle: **0.2.2**, **69,878,550 bytes**; staged per-user update retains pairing/settings.
Validation details are consolidated in this file; earlier split reports are superseded.
The 30-minute synthetic soak completed **62,069 cycles**, checking one final result, bounded tasks and
traced memory growth below its configured 2 MB allowance. It does not certify long-running real capture/playback.
Installed Chrome **158.0.8127.38** and Edge **158.0.4370.33** both passed real local-origin health 200 / unauthenticated denial 403 / invalid-content denial 415 readability checks against installed companion **0.2.2**. These were isolated read-only probes, not native pairing/voice or hosted permission tests.

The existing browse smoke passed on owned Chromium **156.0.8078.4**, pinned browse/extension **0.1.5**.

| Remaining item | Why it is not marked complete | Concrete next input/check |
| --- | --- | --- |
| Slack live send | User explicitly chose **implement/test locally; live Slack later** | Later configure token/scopes/channel membership and explicitly approve one harmless file/destination |
| Final installed physical voice + approval trial | User explicitly chose to test the updated physical flow later; earlier M0 already passed | Run the guided steps later; do not count this deferred trial as passed |
| Pronunciation ratings, physical loopback, 50-run distributions/live soak | Requires listeners, real mic/headphones/loopback configuration and recorded measurements | Collect real per-language/device/network observations; do not relabel synthetic runs |
| Clean Windows 10/11 install and setup time | Current machine has developer prerequisites/caches and saved permissions | Independent clean user/VM/device; signed binary may also need SmartScreen review |
| Public HTTPS Chrome/Edge loopback permissions | No staging/production deployment or actual origin exists | Deploy approved HTTPS environment, configure exact origin, test allow/deny/offline there |
| Public signing/download/release | No trusted signing identity, release channel or approved hosted destination supplied | Organization-owned certificate/signing service and actual download hosting |
| Duplicate-launch behavior probe | Automatic approval review rejected the optional second companion launch with `blocked by policy`; no bypass was attempted | Verify manually later if desired; mutex code is implemented |
| Remote GitHub CI | Publication is now authorized; a remote pass must come from actual Actions results | Check the published PR checks; never infer a CI pass from local tests |
| Production sign-in | Explicitly user-owned dependency, absent in existing product | Trusted session/principal/revocation adapter; preview role must not substitute |
| Live reasoning/GitHub review workflow | OFA Engine explicitly deferred | Implement Engine and exact PR revision/context binding in that separate scope |
| Arbitrary UI semantics / WhatsApp message sending | Outside current bounded command pack; target/recipient/send rules are not implemented | A separately specified action pack, explicit scopes, structural targets and delivery readback |

Operational limits remain explicit: supported Windows/installed apps only; Store/portable/foreground activation
exceptions can still occur; multiple-window close refuses an ambiguous target. Engine retains bounded task
history and 1,000 command deduplication entries per process; checking outcomes and restarting the helper
retains pairing but clears volatile task history. Speaker mode is gated, not full echo cancellation.

## 9. Guided final manual check (user deferred until later)

1. Open `http://127.0.0.1:3000/desktop`, connect if this browser has not paired, and check the Windows origin/key prompt.
2. Keep OFA open, switch to an ordinary website, press physical Caps Lock and say `Open Slack` or `Open VS Code`.
3. Try `Open Claude Code`, then `Open Chrome and navigate to ChatGPT`. Expect a dispatch acknowledgement for URLs.
4. Back in Desktop Integration, enable window controls and approve the separate native permission. Try minimize/restore.
5. Choose a harmless test folder with **Choose write folder**. Say `Write Hello from OFA to Notes dot md`.
6. Inspect the exact path/text/version card, approve it, then say `Read Notes dot md` and check the file/readback.
7. Try a pending write again and press Stop before approving. Confirm no new write occurred.
8. Stop voice, reload OFA, and restart the companion. Pairing should remain; recording must stay off until Caps Lock.
9. Slack is excluded from this live trial as requested. Do not use a real channel/token merely to complete this checklist.


## Development build evidence

- Version **0.2.2**; ZIP **69,878,550 bytes**, generated locally and excluded from Git.
- SHA-256: `FEBEBE6CEF8103C1C07F8F2CEBCEFA6C0AE852B4BFA1E49B46C5A085CFCE32F2`.
- Frozen fake smoke exit 0; **50 bundled feature modules matched current source**.
- Installed host health reports Windows, local-development identity and `llm_enabled=false`.
- Repeated per-user updates retained protected settings; startup stayed off.
- Secret value comparison found **0 matches across 99 feature/report files** before consolidation; values were never printed.
- Local cold probes: Deepgram STT first event 3.078 s, Deepgram TTS first audio 2.047 s,
  Gradium TTS first audio 1.422 s. Current first-event deadlines 4.5/3.5 s avoid false cold failover.
  These are individual network probes, not achieved latency targets or physical p50/p95.

## Remaining product roadmap and handoff

The earlier execution foundation is already in staging and is reused here. Its typed plans, UIA/DOM hands,
file scope, approvals, takeover/stop and evidence are not an independent voice or production-auth product.
Next work needs explicit targets/evidence for broader app/window layouts, multilingual error feedback,
portable/Store exceptions, authenticated websites, form/file dialogs, messaging delivery and durable
external-outcome recovery. LLM reasoning may only enter explicit complex reasoning nodes after Engine
integration; routine actions must remain model-free even then.

Persistent EBrain routines/demonstrations, phone/Telegram, watchers, OAuth connector breadth, voice cloning,
OpenClaw/Hermes integration and broader OS support remain future scope. No cloud database/model/account
provisioning or closed-agent reverse engineering was required for this iteration. User instructions override
the old attached planning document's proposed sequencing and deferrals. Do not reintroduce obsolete
requirements such as Electron, a model classifier for simple commands or sign-in as a blocker to local M0.

Key code: API `voice/` (audio/providers/session/router/pairing/runtime), `ofa_execution/` (shared Gate/hands),
`scripts/` (setup/probes/soak/package/install), `tests/voice/`, `requirements-voice*.lock`, and the Windows
voice workflow. Web: `src/lib/voice/`, `src/components/voice/`, global layout/Settings integration, `/desktop`
and `tests/desktop-voice.spec.ts`. No speech secrets, recordings, local environment or ZIP is part of the PR.

## Publication record

Account: **jvsing**. Both PRs target **staging only**; no merge, deployment or public release is requested.
Descriptions and review comments must use Hinglish and state the implemented backend-heavy
speech-to-action-to-speech scope, the real M0 evidence and the large remaining use-case/edge-case surface.
The workspace report will record both final PR URLs and observed CI status once created.


## Caps Lock liquid-orb popup fix (0.2.3)

The former 340x96 blue concentric-ring Tk popup was a separate native renderer,
not PR #8's extension UI. It is replaced by the PR #8-style top-center rounded
OFA panel, using that PR's actual liquid-orb media at 3x playback. The bundled
240px GIF preserves aspect ratio and circle crop and scales to monitor DPI;
there is no runtime Pillow/ffmpeg dependency or new browser extension requirement.

Showing the popup does not request keyboard focus. Explicit input clicks enable
focus; Enter submits to the already-armed native session and existing router/gate.
Typing never silently arms an idle microphone. Close/mic stop voice, speaker
interrupts the current response, and Open workspace opens local desktop settings.
Caps Lock remains the native single-press activation/stop binding; copying the
extension's double-tap Web Speech preview would create a second capture pipeline.
The native popup does not pretend it can read the foreground webpage.

A native screenshot was inspected locally (excluded from Git per workspace policy). Owned Tk
animation/input/IDLE-hide tests passed; non-interactive voice/execution subset:
108 passed, 3 interactive tests skipped. Final packaged/restarted-host checks are
recorded in the UI-fix PR. Physical user speech rerun is not inferred from UI tests.
