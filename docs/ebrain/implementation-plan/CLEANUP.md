# Completed workspace cleanup and recovery

The owner explicitly requested cleanup of the tournament, offline voice prototype and redundant files. Their later instruction supersedes the research handoff’s earlier preservation restrictions. The cleanup is **recoverable**: obsolete originals were moved outside the active workspace after a source archive and retained-file hashes were verified. No product logic, application-data SQLite database or existing web voice feature was deleted.

## Final active workspace

```text
voice-agents/
  one-for-all-api/
    ebrain/                         existing product code
    docs/ebrain/implementation-plan/ this plan and evidence
    docs/ebrain/SPEC_DEV_BRAIN_V3.md preserved owner spec, corrected filename
    tools/ebrain/legacy/            retained frozen research/evaluation assets
    tools/ebrain/scripts/           active validation/benchmark entry points
  one-for-all-web/                  existing app, owner changes preserved
  20261123-0935-35.2398015.mp4       referenced homepage source media
```

## Disposition

| Original | Current disposition | Reason |
| --- | --- | --- |
| `ebrain-tournament/FINAL/` | `one-for-all-api/tools/ebrain/legacy/FINAL/`, frozen retained bytes | Authoritative legacy spec/reference/variants/CSV evidence, not active product code |
| `ebrain-tournament/benchmark/` | `tools/ebrain/legacy/benchmark/`, excluding venv/caches | Harness/tests/facts-generation CSV inputs retained; create fresh interpreter environment if needed |
| `ebrain-tournament/results/` | `tools/ebrain/legacy/results/`, excluding disposable `_probe_tmp`/caches | Prototypes, probes, scripts, raw CSVs and long-run logs retained for provenance |
| `ebrain-tournament/judge/` and top-level STATE/CODEBASE_MAP/BUILD_PROMPT | Retained in the same legacy layout | Historical result interpretation/hash context |
| Tournament clones, rounds/teams, exchange, orchestration/tools | External archive/original retired folder only | Research competition scaffolding is not a product dependency |
| `local-voice-assistant/` | External `retired-folders/local-voice-assistant/` | Superseded offline app; current API voice bridge retained |
| Four root JPG/PNG/screenshot files | External `root-media/` and source ZIP | No exact filename reference found in active API/web; originals recoverable |
| Misnamed `docs/ebrain/SPEC_DEV_BRAIN_V2.md` | Identical contents at `SPEC_DEV_BRAIN_V3.md`; old file externally archived | Header is V3 and matches Downloads V3 byte-for-byte; no true V2 source invented |
| Root MP4 | Kept in place | `public/media/home-gaze-manifest.json` and homepage test refer to its source name; source asset is not redundant evidence |

The retired top-level folders no longer exist inside `voice-agents`. Generated dependency caches/venvs in the retired originals remain only in the external recoverable folder; they are not copied into the API source tree. No broad “unused file” deletion was attempted in active API/web because unrelated app features and dirty owner files are valid work.

## Recovery location

Sibling directory: `C:\Users\jaiva\OneDrive\Desktop\voice-agents-cleanup-backup-20261124\`.

- `retired-workspace-source.zip`: 21,706 source/research/media files, verified entry-by-entry SHA-256 before retirement. Excludes venvs, git internals, node_modules, caches, temporary benchmark DBs and environment files.
- `manifest.json`: original source paths, sizes/hashes and exclusions.
- `retired-folders/`: full original tournament and offline app moved intact, including excluded disposable runtime directories; use only for deliberate recovery, not current commands.
- `root-media/`: original four images. `SPEC_DEV_BRAIN_V2-misnamed-original.md`: old filename copy.

Inspect/archive contents into a separately named recovery directory first; do not extract over active repositories or overwrite current owner work. Restoring a venv’s path does not make it a supported product runtime. [relocation-manifest.json](evidence/relocation-manifest.json) verifies 150 files retained in the API and the source ZIP; [cleanup-result.json](evidence/cleanup-result.json) lists actual moves. Frozen retained files are unchanged; historical absolute paths inside them are documented, not silently rewritten.

## Dependency repairs and verification

New active wrappers resolve paths relative to the API root and configure exact facts CSV inputs. Current product adapter imports actual `ebrain.store` and records product code hashes, avoiding reference/current import collisions. API README and this plan point at the retained paths. Historical handoff/spec/logs keep original path context. Product source has no runtime import/reference to the retired offline app or tournament folder.

Run the plan validator, full backend with configured measured sources, frozen harness tests, separate reference/product benchmark smoke runs and web checks. Actual results are recorded in [the evidence ledger](evidence/current-checks.json). Initial dirty owner files and retained spec bytes are verified in [owner-files-preserved.json](evidence/owner-files-preserved.json).
