# OFA - Local execution implementation plan

## 1. Current authority and objective

The developer's **Final Scope Correction: Execution-First, Model-Agnostic Architecture** supersedes the former release-wide prerequisites. The product vision remains a voice-first personal assistant. This milestone builds its local Windows execution foundation. It does not build the complete public product.

Run the browser and native hands against real applications using typed commands, predefined structured plans and deterministic/mock planner adapters. Keep the engine independent of input modality, reasoning provider and future production identity. A successful fixture run proves execution of that fixture; it does not prove AI interpretation, code review or live reasoning.

Active implementation branch in both repositories: `feat/local-execution-foundation`. Existing unrelated working changes stay untouched. Implementation lives in an isolated feature package in the API repository; the web repository can integrate its published contracts later. A small local control page removes the unfinished website as a prerequisite.

Publication target authorised by the developer: fork PRs from `jvsing` to the **`staging` branch only**, in `OFA-Labs/one-for-all-api` and `OFA-Labs/one-for-all-web`. Use focused multiple commits; preserve the current scope and document limitations in simple Hinglish.

In this shared workspace, another workflow switched the original checkouts to its E-Brain branch. The active feature worktrees are **`.worktrees/local-execution-api/`** and **`.worktrees/local-execution-web/`**, both on `feat/local-execution-foundation`. Use these directories for this work. The shared checkouts were left on that other workflow's branch; only byte-verified copies of this feature's new files were moved out of them. A normal future pull uses ordinary repository paths.

## 2. Scope classification

Use these classifications consistently: **Implement now**, **Future integration**, **Optional**, **Conditional dependency**, **Genuine blocker**. A requirement can contain a current execution core and a deferred production portion; the classification table makes that split explicit.

### Implement now

- Windows application discovery (registry App Paths and explicit configured executables), launch/reuse and process/window verification.
- Bounded Windows UI Automation observations; structural element identification; semantic invocation/value setting; SendInput typing; focus checks and target-window capture where expressly consented.
- Local browse MCP connection and paired extension; session-owned grouped tabs; structural DOM observations, element clicks/fills/scrolls, navigation and owned-tab closure.
- Narrow allowlisted UTF-8 text-file reads/writes with size bounds, exact-version approval, atomic replace and readback.
- Typed deterministic commands and provider-independent structured multi-step plans.
- One local orchestrator and one rules gate. Hands never plan, approve themselves or decide completion.
- Missing-information errors/questions, human-only handoffs, consequential-action cards, fresh-read comparison, signed single-use approval grants, bounded in-memory effect records, verification and honest unknown outcomes.
- Local authenticated loopback API, browser/Origin restrictions, explicit app/folder/origin consent, emergency stop, pause/resume/cancel and global hotkey.
- Visible task progress, observations, questions, cards and event timeline in a local control page.
- Reproduction instructions, real Windows/browser integration tests and isolated regression tests.

### Future integration

Live model adapters and provider authentication; BYOM UI; vision-language models; speech/STT/TTS/Gradium transport; public signup/Google authentication; production device pairing/authorisation; OAuth connectors; Telegram/phone surfaces; watchers; E-Brain/persistent memory; long-term history; cloud infrastructure; distribution/store publication/release operations.

No Qwen model, Ollama, API purchase, provider key, Postgres, Redis, Supabase, pgvector, hosted domain, cloud storage or telemetry account is required for this milestone. Do not change infrastructure belonging to other OFA modules.

### Optional

Deterministic OCR/image-processing utilities when a real structural target cannot otherwise be identified; additional allowed apps/file formats; developer convenience scripts. OCR never grants permission or authorises a guessed click.

### Conditional dependency

- `comtypes==1.5.0` only for Windows UIA; other hands remain testable without it.
- A runnable pinned `@opencode/browse@0.1.5` binary plus its paired extension for the primary browser route.
- An own Nanobrowser-derived MV3 extension only after a reproduced browse incompatibility prevents required execution. Preserve Apache licence/NOTICE/modification attribution; remove its planner/model/approval logic.
- A bounded local crash-intent journal only if durable crash resume becomes an expressly required feature. Do not introduce a database for speculative future requirements.

### Genuine blockers (scoped to the affected capability)

An absent/blocked application, denied native accessibility/input rights, unpaired/blocked browser hand, missing explicit local app/folder/origin consent, protected credential/security prompt, structurally unidentified element, failed masking/capture, or an unverified/ambiguous external effect. Report the limitation or hand off. Missing voice/models/public auth/cloud services are **not** blockers.

## 3. Concrete implementation layout

All current implementation is inside `one-for-all-api/`, independently importable from E-Brain/voice:

```text
ofa_execution/
  contracts.py              # strict command/plan/action/observation/error contracts
  config.py                 # nonsecret app/folder/origin consent
  planner.py                # deterministic grammar + mock planner + future adapter seam
  engine.py                 # serial orchestration, questions, approvals, progress/control
  policy.py                 # sole gate, fresh-reading hashes, signed one-use grants
  verification.py           # actual readback assertions
  windows.py                # App Paths, process/window identity, UIA, SendInput, capture
  files.py                  # bounded local text-file read/approved atomic write
  mcp.py                    # local stdio MCP transport; no model/tool composition
  browser.py                # constrained browse adapter; fixed DOM collector/templates
  hotkey.py                 # local emergency stop independent of HTTP/voice
  takeover.py               # scoped native input activity; no key text recording
  api.py                    # isolated authenticated loopback control API
  __main__.py               # local launcher, generated session credential, consent flags
  testpad.py                # disposable real Win32 fixture
  config.example.json       # empty allowlists, no secrets or invented machine paths
  ui/{index.html,control.js,control.css}
requirements-local-execution.txt
tests/local_execution/{test_core.py,test_windows.py,...}
tools/local_execution/      # real browser smoke/reproduction helpers
docs/local-execution/{IMPLEMENTATION_PLAN.md,DEVELOPER_INPUTS_REQUIRED.md,HANDOFF.md}
```

The same planning documents remain under `reports/implementation/` for the workspace handoff. Their repository copies make a later API pull independently usable. Do not turn existing E-Brain project-memory identities, experimental database work or dictation code into dependencies.

The web repository is on the matching feature branch. Its production preview is not converted to a release-ready product in this milestone. Future web integration uses the local feature's contracts; no existing web source change is necessary merely to run the local control page.

## 4. Exact execution and integration boundaries

The authoritative current types are `ofa_execution/contracts.py`; reject unknown fields. All current API paths are local feature contracts, not deployed public endpoints.

- `Command {command_id,text,source:"typed"|"voice"}`: current deterministic grammar supports `open <allowed app>`, `browse <allowed URL>`, `read file <allowed path>`. Unsupported language returns an explicit limitation; it is not secretly sent to a model.
- `Plan {schema_version,title,source,allowed_origins,steps[]}`: immutable deep copy at submission. Source distinguishes `structured`, `deterministic`, `mock_planner`, future planner. Maximum 50 steps. Observed page/file text cannot add operations/origins/recipients.
- `Step {id,operation,target,text?,url?,direction,expect?}`: discriminated finite operation set, no arbitrary script/shell/tool name. Target identifies configured app, owned tab, exact structural ref/name/role or allowed file.
- `Expectation {kind:"changed"|"value"|"text"|"url"|"file_text",value?}`: mutations require an outcome assertion.
- `Observation {id,surface,identity,elements[],complete,frame?,facts}`: at most 300 native/browser nodes; bounded depth/frame/file sizes. Elements carry stable generation-scoped refs, role/name/safe value/protected flag/bounds/structural metadata.
- `Outcome {status:"verified"|"unknown"|"handoff",observation,evidence[]}`: verified requires independent fresh readback, never a tool's success claim.
- `ExecutionError {code,message,options[]}`: stable safe errors, including unsupported operation, ambiguity, stale state, missing permission, disconnection, held/cancelled and verification failure.
- `Decision {command_id,approval_id,reading_hash,approve}`: first decision wins; matching exact fresh reading and one task/step/epoch/action only.
- `Control {command_id,action:"pause"|"resume"|"cancel"|"stop"|"continue",handoff_id?}`: idempotent; Continue must identify a human handoff.
- `PlannerAdapter.plan(command,capabilities)->Plan`: future provider obtains authorised access elsewhere and returns structured data only. No provider SDK/auth/model-serving code is implemented now.

Hands expose `capabilities()`, `observe(step)`, `execute(step,before,checkpoint)`. Desktop/browser also validate structural targets before approval. Execution receives a stop checkpoint, never a model handle or approval UI authority. Browser templates are compiled fixed code; callers cannot supply JavaScript, CDP, selectors that execute code, coordinate batches, shell strings or arbitrary MCP tools.

### Local API

```text
GET  /api/capabilities
GET  /api/tasks
GET  /api/tasks/{id}
POST /api/commands                       Command
POST /api/tasks                          {command_id,plan}
POST /api/tasks/{id}/decision            Decision
POST /api/tasks/{id}/answer              {command_id,question_id,option_id}
POST /api/tasks/{id}/control             Control
POST /api/control                       Control (stop/resume across tasks)
```

Bind to `127.0.0.1` only. Generate a per-process local bearer credential; the launcher opens the local page with it in the URL fragment and removes the fragment in-page. Never print the token or require a developer to paste it into chat/documents. API requests require the credential; reject foreign Origin/Host, framing and unbounded bodies; serve no filesystem browser. No public identity/account is implied. Production secure pairing is deferred.

### Browser route

Use local `browse mcp`, pin version, disable automatic upgrades for the controlled process, discover tools and refuse unsupported schemas. Only the constrained adapter is exposed by OFA. It owns the session's OFA tab IDs/group; unrelated tabs are never enumerated/read/controlled. Fixed isolated-world DOM code reads structural identity and safe values; password/OTP fields are not read, hidden security metadata is masked/committed. Incomplete frames/shadow content or protected prompts require human help. A final click/fill requires the same local gate and fresh reading.

Important local limitation: upstream browse does not itself validate OFA tokens against an independently installed third-party MCP client. This milestone authenticates and guards OFA's adapter; it does not claim production extension-side isolation or a hardened multi-tenant trust boundary. That enforcement belongs to future production pairing/security work.

Browser screenshot interfaces may report `SCREENSHOT_REDACTION_REQUIRED` until local masking is configured; do not export an unmasked frame just to advertise support. Native consented test-window frames exercise the observation contract now.

### Desktop and file routes

Resolve only configured approved launch identities, never a model-generated path or arguments. Query matching executable/process-start/window/title identity and verify after launch; reuse rather than opening duplicates. UIA semantic operations first, SendInput for identified focused controls when supported. Re-read after every mutation. Password/OTP/security surfaces hand off; no elevation or secure-desktop bypass. Focus loss stops input. Unknown target returns a question/failure; expose a screenshot interface for later vision integration rather than installing a VLM.

Files are currently bounded UTF-8 text in explicit canonical roots. Resolve symlinks/reparse paths; no folder escape. A write compares the approved version, stages locally, checks again, atomically replaces and reads the actual result. No broad Office/Drive integration is implied.

## 5. Gate, approvals, effects and recovery

One rules gate screens every proposed operation against the frozen plan and explicit local scope. Unknown native/browser mutations are consequential; current native clicks/fills/typing/scrolls, browser clicks/fills and file writes park. Even a fill may autosave, so do not assume it is harmless.

Park -> independently read -> code-render exact action and reading -> human tap -> fresh re-read/compare -> signed process-local single-use grant -> consume once -> checkpoint -> one operation -> independent readback. Sign task/step/action/reading/epoch/expiry/nonce with an in-memory session key. Reject modified/reused/expired grants. A changed reading or control epoch rebuilds the card. Reject/stop never silently approves subsequent work. Personal WhatsApp sends and other explicitly human-only final steps remain manual.

The effect record is bounded and **in memory**, scoped to this feature: `intent -> verified | unknown`, with grant/reading/event references. No Postgres ledger, cloud state or persistent memory is introduced. A lost reply after a possible effect becomes unknown and is never blindly retried. A process restart invalidates all grants and loses tasks; do not auto-replay old plans or pretend to resume a durable task. The operator must inspect the actual application before submitting a new request. This is a deliberate current limitation, not durable exactly-once delivery.

Only Tier A fresh readback is implemented as completion evidence now. A tool claim/response alone never completes a task. The future richer A/B+C framework can extend this contract without changing hands.

## 6. Control, handoff and future voice integration

One foreground task, up to three queued; bounded session task/event/command limits. Pause suppresses future input while preserving work. Cancel stops remaining work without undoing an external effect. Emergency stop applies across hands and blocks new tasks until explicit resume. A global hotkey is registered where available; if registration conflicts, show unavailable and retain local page/console control.

Check interruption before dispatch and between individual SendInput characters; an in-flight OS/DOM primitive can finish. Never claim that a remote RPC can be interrupted mid-native call. Record dispatch/hold/readback times in real tests; do not inherit cloud voice latency claims as locally measured results. If a stop/disconnect occurs after dispatch authority was consumed, preserve unknown and require inspection rather than retrying automatically.

Human handoff: login/OTP/CAPTCHA/payment/OS permission/unreadable protected surface -> pause with handoff ID -> explicit Continue -> fresh read -> revalidate. Continue is not approval for a final click.

Future voice mapping, documented in code:
- Final transcript -> Command or future PlannerAdapter.
- Speech-start -> immediate pause/hold, before final transcript.
- Stop/cancel -> Control; scope and idempotent command ID preserved.
- Spoken response -> consume task/question/approval/completion events in existing voice service.
- Read-back-ended/audio-playing/silence/final approval transcript -> a future deterministic voice-approval predicate. Current approvals are tap-only.
- Future vision -> consume Observation/frame and return a proposed structural target; gate/verification remain authoritative.

No raw microphone storage, provider secrets or audio pipeline is added.

## 7. Sequence and acceptance

1. **Contracts and local skeleton:** strict types, in-memory runner/gate, file hand, local control API/page, fixtures. Exit: a real allowed file task parks, commits once and verifies without any AI/account/cloud service.
2. **Native vertical slice:** own disposable real Win32 app, process/window/UIA, approved edit, SendInput, identified button, readback, screenshot and stop. Exit: real multistep plan passes; sparse/protected/unknown operations report accurately.
3. **Browser vertical slice:** pinned browse/paired extension on isolated Chromium profile, owned grouped tab, structural read, approved fill/click, resulting readback, closure, disconnection. Exit: real browser tests pass separately from mock tests. If primary cannot operate, record blocker and use the planned fallback; never silently switch to cloud execution.
4. **Control/fault tests:** signed/reused/changed tokens; idempotent requests; first decision race; queue bounds; pause/cancel/stop during steps; lost reply after commit -> unknown without retry; unsupported and missing information; immutable plan; authenticated local API.
5. **Reproduction/handoff:** pinned minimal dependencies, empty safe configuration, commands/examples, exact executed test results and unresolved limitations. Another developer runs locally from the branch. PR preparation follows local stability; do not commit/push someone else's working changes.

Current milestone acceptance is local functionality, not a public release: real browser/native operations, predefined multistep execution, visible progress, handled questions, approvals, reliable stop, verified outcomes, honest failures and clean future seams. No model inference is asserted.

## 8. Master requirement classification and traceability

The numbered product requirements remain in the overall vision. This table explicitly supersedes the prior plan's claim that every product module is a current release prerequisite. Tests named below are current tests where present; future rows are not claimed implemented.

| Requirement | Classification and current component / consequence |
|---|---|
| FR-01 | Implement now: Command/Plan, Engine, local API; typed and structured input. Future integration: voice producer. |
| FR-02 | Implement now: deterministic rules/error/clarification. Future integration: second model screening opinion; no live model required. |
| FR-03 | Implement now: frozen copied Plan and declared scope, no execution of outside instructions. |
| FR-04 | Implement now: fixed operation-to-hand routing. Future integration: connector-first and reasoning/vision route selection. |
| FR-05 | Implement now: serial task queue, command IDs, pause/resume/cancel; amend/add interpretation is future adapter work. |
| FR-10 | Implement now: App Paths discovery/configured aliases. Optional: broader Start Menu/UWP/protocol registry adapters. |
| FR-11 | Implement now: DesktopHand verified launch/reuse/focus. |
| FR-12 | Implement now: bounded UIA Observation. |
| FR-13 | Implement now: structural target, semantic input/SendInput, readback. |
| FR-14 | Future integration: VLM fallback. Optional: deterministic OCR. Implement now: screenshot seam and honest unidentified-target error. |
| FR-15 | Implement now: human-only handoff/Continue/fresh read. |
| FR-16 | Implement now: local global stop/checkpoints/hotkey. Future integration: voice/phone stop producers. |
| FR-17 | Implement now: explicit app/folder rights and protected exclusions. |
| FR-20 | Implement now: owned grouped browser tabs/open/close. Future integration: product lending/Disconnect UX. |
| FR-21 | Implement now: bounded DOM observations and document-scoped element refs. |
| FR-22 | Implement now: finite approved click/fill/scroll operations. Optional: select/upload after exact file/field contracts. No unsupported tool is advertised as working. |
| FR-23 | Implement now: protected browser prompt handoff/fresh read. |
| FR-24 | Future integration: persistent recorded demonstrations/routines. Predefined plans test multistep execution now. |
| FR-25 | Conditional dependency: Nanobrowser-derived fallback only if browse fails the required local capability. |
| FR-30 | Implement now: sole local gate/authenticated adapter/checkpoints. Future integration: independent production extension-side enforcement. |
| FR-31 | Implement now: conservative consequential-action parking, including unknown effects. |
| FR-32 | Implement now: independent code-built action/reading card. Future integration: production multi-site card/voice code. |
| FR-33 | Implement now: process-scoped signed one-use hash/epoch-bound approval. Future integration: isolated production signer/device claims. |
| FR-34 | Implement now: volatile effect record and no blind retry. Conditional dependency: durable crash-intent journal only for an explicitly added durability requirement. |
| FR-35 | Implement now: Tier A readback required. Future integration: B+C and richer evidence catalog. |
| FR-36 | Implement now: expiry/first decision/idempotency. Future integration: cross-device partial multi-item approvals. |
| FR-37 | Future integration: voice-code approvals; tap-only now. |
| FR-40 | Implement now: bounded numbered correlated local events and task snapshots. Future integration: production event replay transport. |
| FR-41 | Implement now: actual task/hand states. Future integration: website orb/audio/mic states. |
| FR-42 | Implement now: local progress/plan/question/card/observation/control page. Future integration: complete product dashboard/history/reader/privacy UI. |
| FR-43 | Future integration: full Connections page/OAuth/device management. Implement now: local capability/configuration status. |
| FR-44 | Implement now: local setup/consent/hotkey instructions. Future integration: public account/install/pairing onboarding. |
| FR-45 | Future integration: public no-install Reader/cloud Playground. Not a local execution prerequisite. |
| FR-50 | Implement now: explicit narrow allowed origins/apps and sensitive exclusions. Future integration: full category policy UI/catalog. |
| FR-51 | Implement now: no password/CAPTCHA/security/shell/arbitrary-script/coordinate-batch actions; public target URL checks. Owned loopback test fixtures require an explicit separate fixture allowlist. |
| FR-52 | Implement now: protected values excluded, bounded local observations/no raw audio; unsafe browser frames unsupported. Future integration: provider egress/redaction compliance. |
| FR-53 | Future integration: account/provider Delete-my-data. Implement now: volatile process state; no unrelated data/infrastructure modification. |
| FR-54 | Implement now: bounded session/control/effect events. Future integration: paid multi-user quotas/global cloud budget/audit service. |
| FR-55 | Implement now: local correlated bounded events. Future integration: Langfuse/private cloud storage/retention. |
| NFR-01 | Implement now: local interruption checkpoints and measured tests. Future integration: end-to-end speech-start timing. |
| NFR-02 | Implement now: real local progress. Future integration: voice/orb product latency. |
| NFR-03 | Implement now: rules-only gate, fail closed on hand/auth failure. |
| NFR-04 | Implement now: reproducible local setup. Future integration: public signup/pairing timed onboarding. |
| NFR-05 | Implement now: no OFA mutation without a matching local approval; token-negative tests. Future integration: production threat boundary conformance. |
| NFR-06 | Implement now: no success without readback. |
| NFR-07 | Implement now: hand disconnect/unknown/no retry. Future integration: durable task restore; process restart invalidates all current tasks. |
| NFR-08 | Implement now: minimal pinned dependencies and notices; no deferred runtimes installed. |
| NFR-09 | Implement now: no provider keys, local session credential only, browse relay credentials remain local. |
| AC-01 | Implement now: real allowed app verified launch; particular WhatsApp installation/consent is a scoped machine blocker, not reason to delay core. |
| AC-02 | Implement now: exact native/browser structural target plus actual readback; ambiguity/unsupported errors. |
| AC-03 | Implement now: owned test message/action parks, approved single dispatch, verified state; personal WhatsApp final send remains human. |
| AC-04 | Implement now: changed/reused/forged/expired local token tests. |
| AC-05 | Implement now: lost-reply unknown/no retry. Future integration: durable backend crash resume and production windows. |
| AC-06 | Implement now: local stop/pause/cancel/focus loss and timing evidence; Future integration: voice and remote devices. |
| AC-07 | Implement now: human-only step/Continue/fresh read; never password/CAPTCHA/payment automation. |
| AC-08 | Future integration: cloud no-install public product. No blocker for installed local hands. |
| AC-09 | Implement now: correlated task/step/session/approval/reading events. Future integration: durable multi-device audit service. |
| AC-10 | Future integration: production account deletion/Disconnect/provider purge. Local shutdown invalidates grants; it does not claim provider deletion. |

Current test evidence is recorded in the developer handoff after execution. `tests/local_execution/test_core.py` covers real allowed-file approval/readback, changed cards, rejection, controls, idempotency, forged/reused/expired/restarted grants, local API security, unsupported input, mock multistep execution and lost-effect-reply handling. `test_windows.py` exercises real Win32 UIA/input/readback. Real browse testing is a separate integration run.

Executed current feature evidence: **27 local tests passing**; the combined current-head local and existing API regression run is **56 passed, 1 browser opt-in skipped**. The opt-in **real browse test passed separately**, and the same browser harness passed the actual local control-page approval/progress/Stop flow. Native coverage includes minimize/restore/focus, UIA, approved editing/SendInput/invoke, capture, scoped takeover, hotkey and protected-field handoff. These results prove deterministic execution on the tested fixtures, not live AI reasoning or every third-party application's compatibility. See the handoff for exact commands and remaining limits.

## 9. Developer-only inputs

Use the companion DEVELOPER_INPUTS_REQUIRED.md. Current inputs are limited to consented apps/folders/origins, browser pairing/OS restrictions and machine-specific compatibility. Credentials for future modules are explicitly future integration and are not requested now.

Ordinary library, routing, layout and testing choices are implementation decisions. Never ask the developer to provision a model, public auth, paid credits or cloud services merely to exercise the local engine.
