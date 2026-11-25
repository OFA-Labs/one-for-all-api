# M14 web V3 slice — verification evidence

Run directory: `one-for-all-api/docs/ebrain/implementation-plan/evidence/M14-web-v3/20261125T075902`
Working directory for all commands: `one-for-all-web`
No secrets, tokens or owner-localStorage values are recorded here.

## Commands and results

| Command | Exit code | Counts / outcome |
| --- | --- | --- |
| `npm run typecheck` | 0 | `tsc --noEmit`, no diagnostics |
| `npm run check:arch` | 0 | 108 modules, 224 dependencies, no violations |
| `npm run lint` | 0 | 0 errors, 2 pre-existing warnings in `.cache/motion/patch-duration.mjs` (unrelated to V3) |
| `npm run build` | 0 | Build succeeded; `/v3-preview` listed as dynamic (`ƒ`) |
| `npx playwright test tests/e-brain-v3.spec.ts` | 0 | 11 passed, 0 failed (chromium), 15.6s |

Raw output for each command is in the matching `*.log` file in this directory; each log ends with `EXITCODE=<n>`. Playwright used the repo webServer (`npm run preview -- --port 3100`) with no port conflict; no browsers were missing.

## Scope of the run

- New files only; all prefixed `v3-` except the new route `src/app/v3-preview/page.tsx`.
- Runtime guards are the sole acceptance path for schema-3 payloads. No `as` casts in new TypeScript.
- Preview route is labelled PREVIEW, uses synthetic fixtures, and is disabled on non-loopback hosts in production or with `EBRAIN_V3_PREVIEW=off`.
- The E2E suite renders the components in isolation at `/v3-preview`; it does not use localStorage roles as authority evidence.

## Known limits

- These are isolated UI/guard tests, not a live authenticated server-session integration.
- CP14.1 quota accounting, migration/digests, sealed evaluation and owner-supplied price remain outside this slice.
- STATUS/CHECKPOINTS were not modified by this run.

## Follow-up verification (parent agent, same day)

Added the traceability-named Playwright case `M07_states_and_accessibility` and
re-ran the complete V3 web file:

| Command | Exit | Result |
| --- | --- | --- |
| `npx playwright test tests/e-brain-v3.spec.ts` | 0 | **12 passed** (was 11; includes the M07 alias) |
| `npm run typecheck` | 0 | no diagnostics |
| `npm run check:arch` | 0 | 108 modules, 224 dependencies, no violations |
| `npm run lint` | 0 | 0 errors, 2 pre-existing unrelated `.cache/motion` warnings |

No owner files were modified. The slice remains an additive, labelled PREVIEW,
not an authenticated `/e-brain` integration.
