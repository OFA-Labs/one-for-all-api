# Third-party components

- Primary browser executor: [anomalyco/browse](https://github.com/anomalyco/browse), MIT. Local test CLI/extension version: 0.1.5. Keep the upstream licence with any redistributed binary or extension. The smoke harness verifies extension SHA-256 `5527b8e2865068ebd4060c6274ce7633bc06e1d2080fd19974a1cf9c7a7fe18d`; upstream drift requires review rather than silently accepting another build.
- UIA Python binding: comtypes 1.5.0, retain its distribution licence. Windows UI Automation, SendInput and target capture are operating-system interfaces, not a reasoning provider.
- Local API/runtime dependencies are pinned in the feature's requirements/lock files. Browser test tooling is separately pinned in `tools/local_execution/package-lock.json`.
- No Nanobrowser/OpenClaw/Hermes code/runtime is bundled by the current implementation. If the conditional Nanobrowser fallback is needed later, preserve its Apache-2.0 LICENSE/NOTICE, mark modifications and credit the source. Remove its AI/planner/approval authority.

The OFA collector/input templates and local engine are original feature code. They do not reproduce proprietary closed-agent code or assets.
