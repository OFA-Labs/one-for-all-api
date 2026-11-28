# Local execution foundation

This is the current OFA execution feature, independent of voice, live AI reasoning, E-Brain, public authentication and cloud infrastructure. The isolated local service does not replace existing product APIs.

Run from the API repository on Windows with Python 3.12:

```powershell
uv venv --python 3.12 .venv-local-execution
uv pip sync --python .venv-local-execution/Scripts/python.exe requirements-local-execution-dev.txt
.venv-local-execution/Scripts/python.exe -m ofa_execution --test-pad
```

The launcher opens a local authenticated control page and consents only to a disposable native OFA Test Pad. Enter `open OFA Test Pad`, or run the example structured plan. No personal app/folder permission is enabled by default. Review cards before approving each edit/click. Emergency Stop is available on the page and, if registration succeeds, Alt+Shift+J. Close the terminal with Ctrl+C to stop the service.

The local credential is generated per process, passed to the opened page via a fragment, and never printed. Do not paste credentials into chat or documents. Reloading the page loses the in-memory browser credential; rerun the launcher to open a new authorised page. Restart discards tasks and invalidates approvals. Inspect actual app/file state before resubmitting an interrupted effect.

The launchers keep a ledger of dispatched actions in `%LOCALAPPDATA%\OFA\execution-ledger` (identifiers and hashes only). After a restart, a step that was verified is not replayed, a repeated submit command ID runs nothing, and an action whose outcome is unknown stays blocked for `unknown_block_hours` (default 24). Check the application yourself; to lift a block sooner, delete that ledger folder. Set `ledger_dir` (companion: `OFA_EXECUTION_LEDGER`) to `off` to disable it.

Tier A evidence means the goal was read back. `website.open` cannot read the page, so its task ends as `dispatched` with a tier D `dispatch_receipt`, never `completed`. A reading that did not match is kept as tier B.

For custom permissions, copy `ofa_execution/config.example.json` to the ignored `local-execution.local.json`, then add only discovered approved app identities, folder roots and exact allowed origins. `python -m ofa_execution --discover` lists App Paths metadata without granting permissions. Run `python -m ofa_execution --config local-execution.local.json`. Do not provide a shell, generated executable path or unchecked model-provided launch arguments. Additional app compatibility is measured, not assumed.

Typed grammar is deliberately narrow: `open <allowed app>`, `browse <allowed URL>`, `read file <allowed path>`. Structured JSON plans cover the finite operations listed in local capabilities. Desktop `type` inserts at the current caret; `fill` replaces an accessible field. Unsupported targets, frames, protected prompts and unsupported screenshot redaction report limitations instead of guessing.

## Tests

```powershell
.venv-local-execution/Scripts/python.exe -m pytest tests/local_execution -q
```

The Windows test launches only the disposable OFA fixture. It may briefly take foreground focus. It does not attach to your existing Notepad, Chrome, VS Code or messaging windows. Real browser integration is opt-in and skipped by the general test command until its isolated launcher supplies the paired test environment.

For browser tests, obtain the pinned browse package using the documented upstream installation mechanism. The minimal test does not need `browse install` to modify any agent configuration: `npm exec --yes --package=@opencode/browse@0.1.5 -- browse status --json` checks the pinned binary and reports its discovered executable path. Configure `OFA_BROWSE_BINARY` locally with that actual path. It is a nonsecret path, not an API key. The primary personal-browser flow also requires installing/pairing the browse extension locally; never export browser profiles or cookies.

```powershell
Push-Location tools/local_execution
npm ci
npx playwright install chromium
Pop-Location
$env:OFA_TEST_PYTHON = (Resolve-Path .venv-local-execution/Scripts/python.exe).Path
# Set OFA_BROWSE_BINARY to the executable path reported on this machine.
node tools/local_execution/browser-smoke.cjs
```

The smoke harness downloads the reviewed upstream extension version/digest, loads it into an isolated Chromium profile, creates a one-use local pairing challenge without logging it, tests owned local web content and removes only its own temporary profile. `OFA_CHROMIUM_EXECUTABLE` and `OFA_PLAYWRIGHT_MODULE` optionally select existing local test tools. It never loads your personal Chrome profile. Network access is needed only to obtain test dependencies/extension, not for model access.

See [the implementation plan](IMPLEMENTATION_PLAN.md), [developer inputs](DEVELOPER_INPUTS_REQUIRED.md) and [handoff/results](HANDOFF.md). Deferred production security, durable recovery and public product modules must not be represented as implemented by this local feature.
