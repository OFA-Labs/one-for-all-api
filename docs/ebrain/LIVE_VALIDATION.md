# M2 live developer validation

**Status: NOT RUN.** The CLI, actual configured PowerShell commands and a
temporary real HTTP API passed integration tests with synthetic identities.
That evidence does not establish that the owner's live Claude/Codex sessions
or personal-file bootstrap work. M3–M6 are separate, unfinished milestones.

Use this checklist to settle the specific UNTESTED comments in `ebrain/cli.py`.
Record failures as failures; do not remove tags just because a command exits 0.

## Setup and evidence

1. Use matching M2 API/web revisions and the API's pinned Python 3.12 venv.
   Record both commit hashes, Windows/Python/Claude Code/Codex versions and date.
2. Configure the running API and each agent's intended token outside the repo,
   following the README. Never paste token values into evidence or commits.
   Run the API on `127.0.0.1:8765`. Launch each real agent with its own
   `EBRAIN_AGENT_TOKEN`; optionally set `EBRAIN_URL`. Hooks resolve the web
   checkout through `CLAUDE_PROJECT_DIR` and use the sibling API venv.
3. Read `GET /v1/ebrain/limits?project=one-for-all` with the intended identity.
   Record the returned memory count and modes. Keep `heal_mode=propose` and
   `subject_join=off`. Do not overwrite the owner's existing token map or data.
4. Use clearly labelled, non-secret validation notes. Keep raw personal memory,
   transcripts, credentials and database files out of the PR. Evidence should
   contain case IDs, sanitized operation IDs, expected/observed results and
   counts obtained from the API.

## LV-01 — Live Claude and Codex sessions (T-080/T-081)

- [ ] **NOT RUN:** Start or resume Claude Code in `one-for-all-web`. Confirm its
  project hooks are loaded and SessionStart supplies an E-Brain memory header.
  Confirm a known relevant saved architecture decision appears; a header alone
  is not evidence that the required fact was retrieved.
- [ ] Ask Claude to finish a response with a unique marked note, for example
  `Decision: E-Brain architecture validation marker is live-check-A.` Let the
  actual Stop hook run. Confirm a new accepted log entry through the API and
  that maintenance runs after capture. Confirm healing remains proposal-only.
- [ ] Start a real Codex task in the web repo. Confirm it follows the appended
  AGENTS block and invokes the pinned CLI from the sibling API directory.
  Query the unique marker using Codex's token; verify the saved value appears.
  Record a separate decision through Codex and retrieve it with Claude's token.
- [ ] Repeat with an explicitly private non-secret note. Its owning agent must
  retrieve it; the other agent must not. Agent tokens must still receive 403 on
  human-only resolve, approve, confirm/split and rollback operations.
- [ ] In a separate agent process, use an unavailable URL or omit the token.
  Verify pack is empty, work continues and no successful save is claimed.

**Pass:** both real agent applications load/use the bridge; shared/private and
offline behavior match the expected results. Preserve exact app versions and
sanitized evidence. This does not settle retrieval accuracy on arbitrary notes.

## LV-02 — Personal bootstrap and unchanged replay (T-083)

- [ ] Confirm the owner's intended project/identity and existing source files.
  Record the starting API memory count. Do not manually rewrite the notes.
- [ ] From `one-for-all-api`, with the intended agent token configured, run:

  ```powershell
  .venv\Scripts\python.exe -m ebrain import --file ../one-for-all-web/AGENTS.md --file "$env:USERPROFILE/.claude/projects/c--Users-jaiva-OneDrive-Desktop-voice-agents/memory/MEMORY.md"
  ```

- [ ] Compare the reported newly accepted count with the API count change.
  Verify heading/bullet entries outside fenced code have `#L` source anchors.
  Select distinct known facts from both files and retrieve each separately.
  Verify the current values against the original documents locally.
- [ ] Rerun the exact command while both files and their modification times
  remain unchanged. Expect a newly accepted count of 0 and unchanged API count.
- [ ] Verify no unredacted secret appears in packs or history. Store only
  sanitized evidence, never real secret values or personal source contents.

**Pass:** both real files import without edits, selected independent facts are
correctly retrieved and unchanged replay adds no rows. Merely accepting writes
does not prove the imported facts can be found or are current.

## LV-03 — Real-note codes and relocated Markdown (T-083 extension)

- [ ] Build an owner-approved, sanitized set of real-note examples with expected
  facts and revisions labelled before querying. Record the case count and actual
  results; do not invent accuracy rates or replace frozen benchmark facts.
- [ ] Check that generated codes do not collide within the set and that
  legitimate A → B → A revisions retrieve the final A. Respect remember's
  documented second-resolution identity limit for identical text.
- [ ] Use a disposable copy of a source to test inserted/reordered lines.
  Query each expected fact after import and inspect duplicate current chains.
  Line relocation is a known risk; duplicate/stale results are a failure to
  settle this claim, not a reason to enable automatic joining.

**Pass:** report the labelled cases, expected/observed values and limitations.
Leave the relevant UNTESTED claim open if relocation, collisions or retrieval
errors remain. One successful live session is insufficient evidence here.

## LV-04 — Stop fallback, transcript flush and startup coverage (T-080 extension)

- [ ] Record a real Stop event whose final marked assistant message has not yet
  reached its transcript. Verify the fallback saves it.
- [ ] Retry that same event, then allow the real transcript record to flush and
  capture it. Compare accepted counts and operation identities; investigate any
  extra write for the same logical message. The fallback-versus-flushed case
  remains unproven even though same-input retries already pass synthetic tests.
- [ ] Verify no user/tool messages are saved and rejected writes are reported
  without increasing the saved count. Repeat a marked event in a separate
  project and verify it reaches that project without changing the first one.
- [ ] On labelled real tasks, compare SessionStart's broad-query pack with the
  facts the developer expected. Record omissions. The startup pack is not an
  exhaustive project export; use task-specific pack queries when needed.

**Pass:** real event ordering, rejection/replay behavior and observed startup
coverage have recorded evidence. Keep unresolved duplicate/coverage claims
tagged UNTESTED and document a regression before changing the implementation.

## What to update after testing

1. For each case, replace NOT RUN with PASS, FAIL or PARTIAL plus date, exact
   revisions/versions, expected/observed result and a sanitized evidence link.
2. Add the real outcome to `docs/ebrain/DECISIONS_LOG.md` and the relevant PR
   description. Distinguish live evidence from the existing synthetic tests.
3. Update the corresponding `# UNTESTED:` / `settle:` comment with the evidence
   and remaining scope. Retain the tag for every unproven part. Do not remove
   UNTESTED while the function still claims EXPERIMENTAL or any listed claim
   remains unresolved. Never weaken `test_tags.py`.
4. When a failure requires a fix, first add a regression with its stated reason.
   Rerun the M2 bridge command and full backend suite. Run the existing web
   checks when code or configuration changes. Keep the known dictation-hotkey
   failure separate, as required by the build instructions.
5. Do not change `limits_facts.json`, enable subject joining or automatic healing,
   claim real-use accuracy, or mark M3–M6 complete based on this checklist.
   Those claims require their own evidence and milestone acceptance checks.
