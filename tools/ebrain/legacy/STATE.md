# E-Brain Tournament: STATE

The resume point for any later session. It is updated after every phase. The protocol is the E-BRAIN RESEARCH TOURNAMENT MASTER PROMPT v2, which the user pasted on 2026-11-23.

## Execution mode

Real, separate subagents run every role (the Agent tool, run in parallel in the background). No role is simulated by the Orchestrator. The Orchestrator does not design, argue or vote.

## Fixed facts

- Tournament root: `c:\Users\jaiva\OneDrive\Desktop\voice-agents\ebrain-tournament\`
- KB pinned commits: see `kb/registry.md`. Engram d2ce817c, Remcycle be1e27cd, gbrain b8875aab, claude-mnemonic f950786a (all four VERIFIED; KB-04 adopted).
- Benchmark interpreter: `benchmark\.venv\Scripts\python.exe`, which runs CPython 3.11.15 with pytest 8.3.5 and SQLite 3.50.4. uv created it on 2026-11-23; the system has only Python 3.12 and 3.14.
- Benchmark contract v1 is frozen: `benchmark/INTERFACE.md` and `benchmark/harness/api.py`.
- Ledger ID prefixes, neutral so the labels do not reveal the lens: ALPHA = `P7-`, BETA = `R2-`, GAMMA = `T5-`.
- Judge blinding: the seeded shuffle maps alpha/beta/gamma to Spec-X/Y/Z. The sealed key is in `.orchestrator/sealed/blinding_key.json`, and the Judge must not read `.orchestrator/`. Commitment: sha256 = `b72d181f4e87dd03561b893a9908aec4bde79f57518ad361fe23b0c98f4d916e`. The key is revealed only after `judge/scorecard.md` holds the score table.
- Judge anchors frozen 2026-11-23 11:0x IST, before any spec existed: `judge/anchors.md` sha256 = `CC7FDCB1589D7AC4D31542B6CAE2C7EBA492D0E9A0DAB08EECB521E5DC418AFF` (verified by the Orchestrator). Rulings the Judge made: a tie means a gap of 5.00 or less (INCONCLUSIVE); "Control wins" means Control's Measured Composite (MC) is strictly above every team's; poisoning counts as unmitigated at an injection success of 20% or more overall, or 50% or more in any one attack class; integration paths that don't exist yet are allowed as `new:` paths under an existing parent folder.
- Sealed championship seeds (Phase 7) are not chosen until Phase 7.
- The `existing:<path>` format is relative to `c:\Users\jaiva\OneDrive\Desktop\voice-agents\`, with forward slashes.

## Phase log

### Phase 0: Recon and setup (DONE, 2026-11-23 ~11:05 IST)
- CODEBASE_MAP.md is complete; Recon verified all 141 `existing:` paths. Key facts:
  - The web app is Next 16.4.6 with React 19.3.1 and TypeScript 6. State lives in a single React context, `useApp` in app-provider.tsx; there is no state library.
  - The e-brain placeholder is `one-for-all-web/src/features/e-brain/components/e-brain.tsx`, which returns null.
  - dependency-cruiser forbids imports from one feature into another.
  - The app makes no fetch calls and reads no env vars, and journeys.spec.ts fails on any request to an outside domain.
  - one-for-all-api holds only a README, and there is no one-for-all-core repo.
  - local-voice-assistant is an offline Python 3.12 assistant (Faster-Whisper, Ollama, Kokoro) and is not a git repo.
- done: KB verified (4/4) and cloned; tree created; registry written; benchmark contract v1 frozen; Python 3.11 venv built; blinding key sealed; `tools/spec_lint.py` written (L1–L6), with 3/3 self-tests passing (`benchmark\.venv\Scripts\python.exe -m pytest tools\tests -q`).
- running: Recon agent (CODEBASE_MAP.md); Benchmark Engineer (harness, Control and naive floor, under the Orchestrator); Chief Judge (writing `judge/anchors.md` blind, before any spec exists); Alpha-1, Beta-1 and Gamma-1 Source Miners (Phase 1 started in parallel, since mining does not depend on the recon).
- 07:10–07:30 IST: every agent was cut off by the account's 5-hour API usage limit. By then CODEBASE_MAP.md and judge/anchors.md had been written; the ledgers and the harness had not. At 11:01 IST all six were resumed with SendMessage and told to write files incrementally.
- Phase 1: the BETA ledger is DONE, with 103 entries: Remcycle 34, Engram 26, gbrain 24, Mnemonic 21. Its key finding is that Engram's follow/ignore self-correction code was deleted in commits a485ae7a and a9701cb6, so the pinned code has no follow-rate tracking. The GAMMA ledger is DONE, with 105 entries: Engram 28, Remcycle 25, gbrain 32, Mnemonic 20. GAMMA found independently that the Engram self-correction loop was deleted in a9701cb6, and that Mnemonic's DetectConflict is never wired in. The ALPHA ledger is still running.
- The ALPHA ledger is DONE, with 103 entries. Phase 1 is complete.

### Phase 2: Exchange (DONE, about 11:40 IST)
- The three ledgers were copied unchanged to `exchange/ledger_{alpha,beta,gamma}.md`, and `exchange/README.md` lists the findings the miners reached independently plus the BM25-vs-graph contradiction.

### Phase 3: Spec and qualification (IN PROGRESS)
- running: the Alpha-2, Beta-2 and Gamma-2 Spec Architects (spec_v1.md + prototype/), and the Benchmark Engineer (harness still being built).
- next: hash and freeze the three specs; relabel them to Spec-X/Y/Z for the Judge; run the qualification gate (anchors §5, G1–G8).
- (superseded) next: when the ledgers land, Phase 2 copies them to `exchange/`; when CODEBASE_MAP.md lands too, Phase 3 launches the Spec Architects.
- blockers: none.

## LEAN PLAN v2 (adopted 2026-11-23 16:07 IST at the user's request: about 40% of the weekly token limit was used, so at least 50% must be saved; the user is moving to Sonnet 5.5)
What changed from the master prompt, and why it saves tokens:
1. Agents are resumed instead of re-spawned. A resumed agent keeps the context it already read, so the big files (ledgers 90 KB, map 65 KB, anchors 44 KB) are not re-read. New agents use the Sonnet model.
2. Specs are capped: spec_v1 at about 400 lines; prototype at 500 lines or less including glue.
3. The harness scope is cut. The subprocess kill and two-process tests (procs.py) are dropped. In their place come an in-process reopen check for durability and two Adapter instances alternating writes on one workdir. Runs: seed 101 only, at 1k and 10k.
4. The qualification gate is mechanical, run by the Orchestrator with scripts: sections a–p present, prototype tests green, `existing:` paths resolve. The Judge does not spend tokens on it.
5. The kill rounds become ONE combined round (all three themes R1–R3). Each team makes at most 2 attacks per rival, each 200 words or less, and gives one written response (REFUTE / CONCEDE / REVISE). That yields spec_v2. Round 3 is skipped and its kill claims are folded into the single round.
6. Phases 5–7 are run by the Orchestrator with shell commands and no agent. The S1–S11 stress tests are part of each harness run. The championship is the top two plus Control on a sealed seed, drawn at run time, at 1k and 10k.
7. The Judge is ONE Sonnet agent. Its inputs are the blinded spec_v1/v2 files, a compact results table and the round record. The permalink audit drops to 8 per spec (this deviates from anchors §6 and is logged as such). Output: scorecard and verdict.
8. FINAL/: the winning team's architect (resumed) writes all 13 files, kept concise. The Cold-Read Gate is one Sonnet Cold Builder with at most 1 repair cycle (instead of 2); after that, BLOCKERS.md.
9. The Orchestrator never reads large files whole (it uses grep/head) and keeps its messages short.

### Phase 3 progress (16:2x IST)
- GAMMA spec_v1 + prototype DONE: adapter 414 lines, 13 tests pass, public-seed 1k runs on 101/102/103 saved under teams/gamma/. It discloses its own misses: zombie_rate 0.10–0.27 and one successful injection on seed 102 (0.17 overall). It also says its text-authority-spoof gate was added after seeing a public-seed failure, so a rival may call it tuned.
- ALPHA and BETA specs: still running. Benchmark Engineer: still running.
- Benchmark Engineer DONE (16:3x IST): harness, Control and naive built; 12 tests pass; 230 rows in benchmark/results.csv (seed 101, 1k and 10k). Control beats naive on both sanity metrics. Runtimes: Control 4.6 s at 1k and 108 s at 10k. Six contract readings are logged in benchmark/CONTRACT_ISSUES.md. Real OS-level concurrency and kill-mid-batch tests are UNMEASURED because procs.py was dropped under lean plan v2.
- Note: Control's zombie_rate is high (0.79 at 1k, 0.97 at 10k) because it does not link silent free-text updates. That is the gap the teams must close.
- BETA spec_v1 + prototype DONE: spec 324 lines; adapter 470 lines; 14 tests pass; public seeds 101–103 at 1k measured: zombie 0.10/0.35/0.36, heal_harm 0.33. Its thresholds were tuned on public seeds only, and the 10k size was not run. Waiting for ALPHA.

### Phase 3 FROZEN (2026-11-23 ~17:00 IST)
Mechanical gate (tools/gate.py): all three specs have sections a-p, no missing `existing:` paths, 0 vague tokens, and green prototype tests (15, 14, 13). All qualify. Frozen hashes:
- alpha/spec_v1.md sha256=d6860950d14788f9546f76ce4359684b876269f1b706219433255a37447d88b3
- beta/spec_v1.md sha256=87ea5f0a3a0bc64bc90e86b99ddf4ff2757646d7d3fa985a93206ed0bccdc9d5
- gamma/spec_v1.md sha256=49365262c85961d09e4e2352a33f90d6490182c07dad69ec25c08491f29feb14
Blinded copies are in judge/blind/Spec-{X,Y,Z}_v1.md.
- Round 1: ALPHA attacks filed (teams/alpha/attacks_r1.md): 2 on GAMMA, 2 on BETA, each with a harness run. Waiting for BETA and GAMMA attacks, and ALPHA's 10k run.
- Round 1: GAMMA attacks filed (teams/gamma/attacks_r1.md): 2 on ALPHA, 2 on BETA. Waiting for BETA attacks and ALPHA's 10k run.

### Phase 4 (single combined kill round, lean plan v2)
- Attacks filed by all three teams (teams/*/attacks_r1.md), 12 total, each backed by a run against a frozen rival prototype. The recurring claims are: Gamma checks path before supersedes (possible hijack/poisoning disqualifier), Alpha's and Beta's healing can demote or merge unrelated facts, and several pre-registered predictions are broken on public seeds.
- 17:3x IST: defence round started (teams/*/defence_r1.md, spec_v2.md if revised). ALPHA 10k run is still in flight (monitor active).
- GAMMA defence DONE: spec_v2.md (hash bd7ba7f08b7f5fe0 -> cb925a7aedb4103a, 16 tests green). Revised the external-hijack and stale-base attacks; conceded beta-G2. Hijack probe 10/10 -> 0/10.
- ALPHA defence DONE: spec_v2.md (code hash f0f368cdb55c8f50, 19 tests green). Revised 3 attacks, conceded 1 (stale summaries still show as current, 0.25/0.25/0.5 on seeds 101-103). Heal harm rose from 0.33 to 0.5 on seed 101, all of it from retrieval misses. Note: ALPHA's kill claim against GAMMA predates GAMMA's v2 fix, which is a point for the Judge.

### Phase 4 DONE; Phase 5/7 started (~18:2x IST)
- All defences are in. Hashes at freeze, with v2 specs sha256 (first 16): alpha C3A2C05078DEC8F9 (code f0f368cdb55c8f50), beta 732C31AD7073D180 (code f38c3148d9351b6f), gamma 5FBB02A4430E9FDF (code cb925a7aedb4103a). Prototype folder fingerprints (first 16): alpha 26a3efb19f1bf032, beta 9c86185ef7daf06c, gamma d4418fe70227640c.
- The stale ALPHA 10k run (it started before ALPHA changed its code) was killed. The final runs on frozen v2 code are: control, alpha, beta and gamma at 1k and 10k on the sealed seed (kept in .orchestrator/sealed/championship_seed.txt), plus 10k on public seed 101. Output: benchmark/results_v2.csv; progress in /tmp/final_done.log. The four contenders run in parallel, so latency was measured under equal load.

### Phase 5-7 DONE (~19:00 IST): final benchmark results in benchmark/results_v2.csv. Sealed seed = 556920. All 12 jobs ran and nothing timed out. Zero leaks, zero acked_lost for everyone. Control leads correct_version_acc (0.97 vs <=0.89 at 1k; 0.84-0.85 vs <=0.67 at 10k); the specs lead zombie_rate, injection and tokens (about 50 vs 490 per bundle). ALPHA's 10k query p95 was 604 ms on seed 101 and 1455 ms on the sealed seed; the others stay under 50 ms.
### Phase 8 (IN PROGRESS): Chief Judge resumed with the blinded evidence pack (judge/blind/, judge/results_summary.md). It writes judge/scorecard.md and judge/verdict.md. Then: reveal the key, FINAL/ compilation, lint, cold-read gate.

### Phase 8 verdict v1 (Judge, ~19:30 IST): INCONCLUSIVE, leader Spec-Y (57.39) over Spec-Z (53.37) and Spec-X (51.97); Control 36.93, DISQUALIFIED for poisoning (injection 0.556, poison/spoof classes 1.0). Nobody was killed, and no spec was disqualified. All 24 audited permalinks OK. The Judge's decisive experiment is to run the two missing sealed seeds; running them now (seeds in .orchestrator/sealed/championship_seeds_2_3.txt, results appended to benchmark/results_v2.csv).
- All 16 extra-seed jobs finished (seeds 878791 and 235664). The Judge was asked to re-score with all 3 sealed seeds. The user then asked to STOP after this re-score.

### Phase 8 FINAL VERDICT (2026-11-23 ~21:50 IST): INCONCLUSIVE, leader Spec-Y. Stopped here at the user's request.
- Key revealed after the scorecard was written: Spec-X=ALPHA (event-sourced (correction loop)), Spec-Y=GAMMA (temporal knowledge graph), Spec-Z=BETA (multi-tier lifecycle).
- Re-score over 3 sealed seeds (Final/100): Spec-Y 59.64, Spec-Z 56.23, Spec-X 18.53, Control 38.21 (disqualified for poisoning, injection 0.594). The Y-Z gap is 3.41, so it is a tie under the 5-point rule; the lead is 3.05 once ARGUED credit is removed. Nobody was killed.
- Spec-X timed out (900 s) at 10k on 2 of 3 sealed seeds, which zeroed its components. Spec-Z failed one rollback probe (14/15), which the Judge replayed and found not to be unrecoverable corruption.
- The decisive next experiment is to build and render the visual-brain pages for Y and Z and score the V1-V10 checklist as measured. Z wins only if it beats Y by more than 4.24 points.
- NOT DONE (user deferred it until the token limit resets): compiling FINAL/ (13 files) with the leader's architect, spec_lint, the cold-read gate, and the full summary.

### FINAL/ compile started (user chose: Spec-Y + experimental reworded-update fix; honesty in code comments + frontend; limit ~1,000 memories). Architect resumed; spec_lint to be run until clean; then a cold-read check.

### FINAL/ DONE and gate PASSED (2026-11-24). Verified by the Orchestrator: spec_lint clean; reference tests 43 passed / 1 skipped on Python 3.11 (52 passed on 3.12 with fastapi). Cold Builder (Sonnet) re-check after the single repair cycle: all 12 blocking items FIXED, 0 new blocking, M0 red as designed (22 failed, 6 passed, 1 skipped, 23 errors), M1 backend 51 passed / 1 failed. The 1 failure is test_spec_amended, which needs SPEC B4.3 in the web repo to be amended (the user must approve that). Nothing was built in the user's real repos (one-for-all-web / -api); all of FINAL/ is spec + skeletons + a reference prototype. No BLOCKERS.md needed.
- Decision still open for the user: amend SPEC B4.3 ('e-brain stays blank') in one-for-all-web/docs/SPEC_ITERATION_1.md around L283.
