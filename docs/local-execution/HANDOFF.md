# Developer handoff — local execution

Branch: `feat/local-execution-foundation`. Matching branch exists in the web repository. Existing unrelated working changes were preserved and are not part of this feature.

Active workspace locations: `.worktrees/local-execution-api/` and `.worktrees/local-execution-web/`. The shared original checkouts were switched/committed by another E-Brain workflow during this task. Feature files were byte-compared and moved to the isolated worktrees, preserving that workflow. Use the feature worktrees for review/testing; do not switch or stage the other workflow's checkouts.

The developer's final correction is controlling: execute locally first; deterministic plans now; model/voice/public identity/cloud integrations later. Start with [README.md](README.md). Current contracts and integration comments are in `ofa_execution/contracts.py`, `planner.py` and `api.py`.

Implemented: isolated local launcher/control page, authenticated loopback API, finite typed/structured commands, bounded in-memory orchestration/events/effects, one rules gate, signed one-use approvals with fresh reading comparison, local file operations, real Windows UIA/SendInput/target capture, primary browse MCP adapter and isolated real-browser harness.

Validation executed on 2026-11-25:

- Fresh isolated Python 3.12 environment installed from the feature-specific pinned requirements; no model/provider/cloud account configured.
- Local suite now contains **27 passing tests** after the PR-readiness regressions. Combined current-head run: `python -m pytest tests/local_execution tests/test_api.py tests/test_cors.py tests/test_store.py -q` — **56 passed, 1 skipped**. The skip is the explicitly opt-in browser test run below. One existing pinned Starlette/httpx deprecation warning; tests pass.
- `node tools/local_execution/browser-smoke.cjs`: **1 real browser integration passed**, using browse/extension 0.1.5 and isolated Chromium 156.0.8078.4. The harness also passed the actual local control-page flow: parked file write, approval before mutation, verified completion/progress and emergency Stop.
- Existing API regression check in this feature worktree: `python -m pytest tests/test_api.py tests/test_cors.py tests/test_store.py -q` — **29 passed**.
- Real Windows fixture coverage: process/window launch verification, minimize/restore/focus, UIA, three separately approved mutations, actual SendInput, button invocation, target-window BMP capture, untagged user-input takeover under the 250 ms test bound, global hotkey registration/message, and password-field handoff with no value read/type/capture.
- Fault/security checks cover changed approval readings, signature/replay/expiry/session restart rejection, first-decision race, immutable copied plans, bounded queue, questions/Continue, local HTTP authentication/Origin checks, private target denial, and lost possible-effect replies reported unknown without retry.

No successful live reasoning, production pairing, model connection, voice integration, cloud release or independent second-machine reproduction is claimed. Native tests use an owned real Win32 application; they do not establish compatibility with an untested personal app such as WhatsApp Desktop.

Review only this feature's package, tests, tool/dependency files and `docs/local-execution/`. Unrelated E-Brain/voice/preview changes are outside this feature diff. The developer authorised focused commits and fork PRs from `jvsing` to **`OFA-Labs/one-for-all-api:staging`** and **`OFA-Labs/one-for-all-web:staging`**. The web companion is documentation only; no production preview wiring is claimed.

PR-readiness follow-ups fixed typed-command retry idempotency (generated step IDs no longer change the deduplication key) and moved plan screening outside the stop/control lock. The takeover timing test now measures the actual input-suppression signal rather than the polling thread's later scheduling time. Real desktop tests need an idle interactive Windows session; user input intentionally pauses them instead of being ignored.

Current limitations: in-memory tasks do not survive restart; ambiguous possible effects are unknown/no retry; supported native control patterns vary by app; personal apps require local consent/configuration; browser screenshot egress is withheld until masking is configured; app discovery starts with App Paths/configured executables; production extension-side gate isolation is deferred. Unsupported operations report errors/handoffs. Full product requirement classifications are in [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md).
