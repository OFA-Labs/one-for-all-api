# E-Brain documentation

## Index (current vs historical vs preserved)

| Document | Classification | What it is |
| --- | --- | --- |
| [Implementation plan — start here](implementation-plan/README.md) | CURRENT ENTRY POINT | Owner-selected V3 path, current code inventory, M7–M14 tasks/checkpoints, tests and coding-agent instructions. |
| [V3 proposed specification](SPEC_DEV_BRAIN_V3.md) | PRESERVED (hash-frozen) | Original owner text under the corrected filename; not a claim of implemented capability. |
| [Research handoff — ARCHIVE](HANDOFF_TO_PLANNER.md) | HISTORICAL / ARCHIVE | Historical experiments and limitations; byte-preserved. Original tournament paths are now under `tools/ebrain/legacy/` relative to the API. |
| [Append-only decisions log](DECISIONS_LOG.md) | ACTIVE | Existing implementation decisions and new superseding ADRs when approved. |
| [Live validation checklist](LIVE_VALIDATION.md) | ACTIVE | Owner application/session checks; synthetic suite success is not live validation. |
| [Individual edition scope](INDIVIDUAL_EDITION_SCOPE.md) and [loophole audit](LOOPHOLE_AUDIT.md) | CURRENT ADDENDA | Current scope classification and the audit of defects actually fixed. |
| [Retained research tools](../../tools/ebrain/README.md) | FROZEN + ACTIVE WRAPPERS | Frozen reference/harness/results, current wrappers and recovery provenance. |

The implementation plan reconciles inconsistent historical milestone/50k/price/authority language. Use actual executed evidence for measured claims and approved versioned ADRs for changed behavior. Byte-preserved evidence is recorded in [owner-files-preserved.json](implementation-plan/evidence/owner-files-preserved.json) and [relocation-manifest.json](implementation-plan/evidence/relocation-manifest.json); do not edit or rename those files or the preserved documents they describe.
