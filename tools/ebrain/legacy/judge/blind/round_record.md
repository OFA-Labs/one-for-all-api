# Round record (blinded): attacks and defences


---
## Spec-X / attacks_r1.md

# Kill-round attacks, round 1

All runs were executed from `benchmark\` with `benchmark\.venv\Scripts\python.exe` on 2026-11-23 against the frozen rival prototypes. Scripts are in `teams/Spec-X/attack_scripts/`, and CSVs are in `teams/Spec-X/rival_runs.csv` (contender-Spec-Y code hash `bd7ba7f08b7f5fe0`, contender-Spec-Z code hash `5906a205a2ad04fa`, size 1000, seeds 101 and 102). Nothing was written to `benchmark\results.csv`.

---

## G1 (Spec-Spec-Y): `supersedes` hijack becomes current, which trips the DQ2 class test

1. **Disputed claim.** §h: "Supersedes hijack | external supersedes always land in the target chain, where T3 blocks them". §c.4 says the same.
2. **Suspected weakness.** `_assign_chain` checks `path` **before** `supersedes`. An external write that carries a path the first-party head never used therefore opens a new chain `p:<path>`. That chain holds only external writes, so its write becomes `current`.
3. **Evidence (MEASURED).** `harness.runner --contender ..\teams/Spec-Y/prototype --size 1000 --seed 102` gave `S6 injection_success_hijack 0.5 n=2` and `ALL injection_success_rate 0.1667`. Tracing that run (`attack_scripts/hij.py Spec-Y 102`) shows the cause. The attack `op-8d84dc29faf5` is external, has path `src/api/supabase_plan_mobile.py`, and has `supersedes=('op-ecb50e531951',)`. That target is a path-less human claim. The bundle then shows `current ('untrusted',) … updated to Free (VC-MHMSFH)` next to the human value `VC-3NB2BH`, which is also `current`.
4. **Failure scenario.** A browser worker report proposes a new "plan" value for a file path. The agent then sees two current values, and one of them is the attacker's.
5. **Consequence.** Tainted content becomes a live value, which violates SPEC B6.2. DQ2 is "≥ 0.50 success within any single S6 attack class", and this run hit exactly 0.50. The spec's prediction "injection ≤ 0.03, disproved if > 0.07" is also broken on a public seed.
6. **Settling test.** Write a first-party human claim with no path, then an external write with a new path that supersedes it, then query. The attack should never be `current`. Then re-run seed 102 and require `injection_success_hijack` = 0.

## G2 (Spec-Spec-Y): T5 stale-base write shown as current

1. **Disputed claim.** §c table: "supersedes names an op that is no longer live | T5 | the stale-base op is never current; the head stays current", marked REPRODUCED.
2. **Suspected weakness.** A first-party write with `supersedes` joins the target's chain only "if the slot terms overlap". A reworded stale write therefore falls through to a new chain, where nothing marks its base as stale.
3. **Evidence (MEASURED).** On seeds 101 and 102, `S2 conflict_acc_t5` is 0.3333 (n=3 each), and `ALL conflict_acc` is 0.6667 and 0.5. Tracing with `attack_scripts/t5.py Spec-Y 101` shows the stale write `op-417031ad3bbe` (codex, `supersedes=('op-15ae6874ee37',)`) rendered as `current () … TTS backend for enterprise tenants: now ElevenLabs [VC-T2VZWL]`. The true head `VC-TVY0KE` is shown `current` beside it.
4. **Failure scenario.** Codex works from a stale read and overwrites Claude's newer decision. Both values then appear as current with no `conflict` flag.
5. **Consequence.** Concurrent agents silently diverge. The pre-registered "conflict_acc ≥ 0.95, disproved if < 0.85" is broken on both public seeds.
6. **Settling test.** Write v1, then v2 superseding v1, then v3 from another agent with reworded text superseding v1. v3 must be non-current or flagged `conflict`.

## B1 (Spec-Spec-Z): one trace note can erase an unrelated correct fact (Standout "correction-anchored slot fusion")

1. **Disputed claim.** §g Fix: "If the note's code belongs to another slot → `merge(slotA, slotB)`; replay of the union then picks the true head". §e: "No age-based demotion … would harm H2/H3".
2. **Suspected weakness.** The merge trusts any value code found in a free-text note, which no one has verified. It has no subject check and no check of its effect on the other slot. The replayed union can retire that other slot's head.
3. **Evidence (MEASURED).** `attack_scripts/merge2.py <Spec-Z prototype>` writes two unrelated specs: Vercel plan `VC-BBBBB1` (ts 2) and wake word `VC-AAAAA2` (ts 5, superseding ts 1). It then adds one codex trace that ignores the wake-word item with the note "used VC-BBBBB1 instead". Output: `before vercel: [('current','(VC-BBBBB1).')]`, then `report … {'action': 'merge', 'targets': [1, 2] …}`, then `after vercel: []  wake: []`. With `merge.py` (Vercel plan written by a human), "wake word?" afterwards returns `current (VC-BBBBB1)`, which is the Vercel plan code.
4. **Failure scenario.** An agent's session note cites the wrong code, by typo or by injection through tool output. Healing then deletes a correct fact from every agent's context, or answers one subject with another subject's value.
5. **Consequence.** This is harm to H3-type memories, and it can be reached by poisoning through traces. P5.B (heal_harm) and the "≤ 0.35" prediction are both exposed.
6. **Settling test.** Run `merge2.py`. The Vercel plan must stay `current` after `maintain()`.

## B2 (Spec-Spec-Z): five pre-registered "both sizes" predictions fail at 10k

1. **Disputed claim.** §o (sealed seeds, both sizes) makes these predictions: correct_version_acc ≥ 0.88, zombie_rate 0.10–0.40, conflict_acc ≥ 0.80, asof_acc ≥ 0.70, and query_p95_ms @10k ≤ 50.
2. **Suspected weakness.** Slotting by IDF-weighted Jaccard ≥ 0.4 (§c.5) does not hold up as the corpus grows. Same-subject versions land in different slots, so several values show as `current` for one fact, and as_of and conflict replay look at incomplete chains.
3. **Evidence (MEASURED).** `harness.runner --contender ..\teams/Spec-Z/prototype --size 10000 --seed 101 --out ..\teams/Spec-X/rival_runs_10k.csv` (run `contender-Spec-Z-10000-101-20261123T105551Z`, hash `5906a205a2ad04fa`) gave correct_version_acc 0.557, zombie_rate 0.5217, conflict_acc 0.2 (n=60), asof_acc 0.448 (n=125) and query_p95_ms 59.384. All five miss their disproof lines. The mechanism is already visible at 1k: `attack_scripts/asof.py Spec-Z 102` shows "primary region for the voice worker" with both `VC-G29C5B` and the true head `VC-2DDR2Y` as `current`.
4. **Failure scenario.** In a large archive (S7: 10k memories, 40% logs), an agent asking for the current setting gets two contradictory "current" values about half the time.
5. **Consequence.** In ONE FOR ALL, Claude, Codex and the voice agent would act on stale settings, and time travel would not tell them what was believed when an agent acted. This hits P1.A (S7@10k), P6 and P8 together.
6. **Settling test.** Run the same command on the sealed seeds at 10k. Any mean below the §o lines confirms the disproof.


---
## Spec-X / defence_r1.md

# Defence, round 1

All runs were from `benchmark\` on 2026-11-23. v2 prototype code hash `f0f368cdb55c8f50`, 19 tests pass. Public-seed results are in `teams/Spec-X/public_runs_v2.csv` and `spec_v2.md` Appendix D. I re-ran each attacker's script myself, and all four attacks reproduced on v1 (hash `780da809e9d1`).

## Spec-Y A1 (a cue word alone demotes a correct memory): REVISE

**Valid.** `..\teams/Spec-Y/atk_r1.py` on v1 printed `s1_cue_only_demote … actions=['demote'] after=[]`.

**Principled fix.** A cue word is not evidence, so the `CUE` path was removed. `evidence()` now demotes only when one of these holds:
- the note names a different value code about the **same subject**: its origin write is in the memory's chain, shares ≥ 0.2 of its slot words, or is a newer write at a path the note names;
- the note names the memory's own path.

**After the fix.** The same script prints `actions=[] after=['VC-OTP006']`, and the `s3` unrelated-code case also gives `actions=[]`. New test: `test_v2_cue_word_or_unrelated_code_is_not_evidence`. stale_demotion_recall is still 1.0 / 1.0 / 1.0.

**Settling test.** Use Spec-Y's own: H2 traces with each cue word must give 0 demotes.

## Spec-Y A2 (cross-chain `supersedes` overwrites an unrelated fact): REVISE

**Valid.** v1 printed `s2 auth=['VC-VERCTM']` and `s4 auth=['VC-REFR14']`.

**Fix.** A first-party `supersedes` joins the target's chain only if the write shares ≥ 1 slot word with it and no other chain matches better (≥ 0.6 and higher). Otherwise it is ignored, as INTERFACE §2 does. External writes still always join the target, where T3 quarantines them.

**After the fix.** `s2 auth=['VC-AUTH45']` and `s4 auth=['VC-AUTH45'] refresh=['VC-REFR14']`. Tests: `test_v2_cross_chain_supersedes_is_ignored`, `test_v2_near_miss_supersedes_goes_to_own_subject`, and `test_v2_reworded_stale_base_still_joins`, which keeps T5.

**Remaining gap.** In `s2` the old Vercel value `VC-VERCPR` is still current next to `VC-VERCTM`. This is the known weakness 1 (a split chain), not a hijack.

## Spec-Z A1 (an agent write erases a human decision): REVISE

**Same root cause as Spec-Y A2, same fix.** `..\teams/Spec-Z/attacks\hijack_probe.py Spec-X` printed `'which STT provider?' [('x1','current')]` on v1. On v2 it prints `[('h1','current',())]`, and the hijacking write stays only under `'wake word?'`.

**Settling test.** Spec-Z's own: h1 must be current in ≥ 9 of 10 subjects.

## Spec-Z A2 (S10 summary zombies break the prediction): CONCEDE

**Valid.** S10 `zombie_rate` was 0.25 / 0.25 / 0.75 on v1 and is 0.25 / 0.25 / 0.5 on v2, against my pre-registered "≤ 0.05, disproved if > 0.10".

**Cause.** Copies correctly inherit the status of their origin. The origin itself is a zombie, though, because the chain is split (weakness 1). That split needs slot canonicalisation (the batch Haiku step), and I did not tune a threshold to hide it.

**Action.** The prediction was revised in `spec_v2.md` §o, and the disproof is kept on record.

## Kill claims

- **Spec-Spec-Y:** an external `supersedes` hijack that carries a new path becomes `current`. Seed 102 measured `injection_success_hijack` = 0.5 (n=2), the DQ2 single-class threshold, and Spec-Z's probe shows 10/10 trials (`attack_scripts/hij.py Spec-Y 102`).
- **Spec-Spec-Z:** at 10k on seed 101, contender-Spec-Z measured correct_version_acc 0.557, zombie_rate 0.52, conflict_acc 0.2, asof_acc 0.448 and query_p95 59 ms, which breaks five pre-registered "both sizes" predictions. Separately, its `merge` heal erases an unrelated, never-ignored fact (`attack_scripts/merge2.py`: `after vercel: []`).


---
## Spec-Z / attacks_r1.md

# Attacks, kill round 1 (Team Spec-Z)

Harness runs are in `teams/Spec-Z/attack_runs.csv`: contenders `contender-Spec-X` (Spec-X, code_hash 780da809e9d13a7d) and `contender-Spec-Y` (Spec-Y, code_hash bd7ba7f08b7f5fe0), seeds 101–103, size 1000, harness 1.0.0. Command, from `benchmark\`: `.venv\Scripts\python.exe -m harness.runner --contender ..\teams\<t>\prototype --size 1000 --seed <s> --out ..\teams/Spec-Z/attack_runs.csv`. The probe scripts are in `teams/Spec-Z/attacks/`. Every output below is what the runs actually printed. Tier: MEASURED.

---

## A1 → Spec-X: an agent write erases a human decision through a cross-chain `supersedes`

1. **Disputed claim.** §f L79: "T2 (lower authority without naming a live op → `superseded`)". §h L112 lists `supersedes` hijacks as defended, but only for external writes.
2. **Suspected weakness.** `_assign_chain` (`teams/Spec-X/prototype/adapter.py` L212-L216) puts a write into any chain its `supersedes` names, with no check that the subject matches. A first-party agent write about another subject can therefore join a human chain, name the live op, and pass T2.
3. **Evidence.** `python ..\teams/Spec-Z/attacks\hijack_probe.py Spec-X` writes a human decision "STT provider is Deepgram (VC-HUMAN1)", then a codex claim "The wake word is Hey Chitti (VC-HIJAK1)" with `supersedes=("h1",)`, then runs `maintain(3)`. It printed `'which STT provider?' [('x1', 'current', ())]`. The human value is gone. Spec-Y and Spec-Z both return `h1 current` for the same input.
4. **Failure scenario.** Any agent, or a confused or poisoned one, can delete a human decision by citing its op_id in an unrelated note.
5. **Consequence.** B6.7 ask-budget answers, which are human facts, can be wiped without anyone seeing it, so the voice agent acts on the wrong value.
6. **Settling test.** Run the probe across 10 subjects: Spec-X must show `h1 current` in at least 9 of 10.

## A2 → Spec-X: summary and restatement zombies break the S10 prediction

1. **Disputed claim.** §o: "zombie_rate[S10] ≤ 0.05 … Disproved if > 0.10". §f: "Summaries never become head over a primary version (T7)."
2. **Suspected weakness.** Copies inherit the status of a chain-local version, so a restated superseded code still shows as current whenever chains are split.
3. **Evidence.** In `attack_runs.csv`, S10 `zombie_rate` was 0.25, 0.25 and 0.75 on seeds 101–103 (n = 4 each), and S10 `summary_zombie_rate` was 0.0, 0.25 and 0.25.
4. **Failure scenario.** An agent recap repeats an old TTL, and that old code comes back as `current`.
5. **Consequence.** A wrong summary written by one agent misleads every other agent, which is P5.C and P1.C.
6. **Settling test.** Sealed seeds: S10 `zombie_rate` must be ≤ 0.10 mean on every seed, as Spec-X pre-registered.

## G1 → Spec-Y: an external hijack with a path skips the T3 defence (10 of 10 trials)

1. **Disputed claim.** §c L49: "for an **external** write, always join the target's chain, because T3 then neutralises it; this is the hijack defence". §h L115: "external supersedes always land in the target chain".
2. **Suspected weakness.** `_assign_chain` (`teams/Spec-Y/prototype/adapter.py` L203-L204) returns `"p:" + w.path` before it looks at `supersedes`. An external write that carries a new path gets its own chain, where it is the only version, so it becomes `current`.
3. **Evidence.** `python ..\teams/Spec-Z/attacks\external_hijack_probe.py Spec-Y` writes a human fact, then an external "Worker report …" with a path and `supersedes`, then runs `maintain()` and queries, over 10 subjects. It printed `trial 0 current items: [('h0', ()), ('x0', ('untrusted',))]` and `Spec-Y: external code shown current in 10/10 trials`. Spec-X and Spec-Z scored 0/10. In the harness, `S6 injection_success_hijack` was 0.5 on seed 102 (n = 2), the same Supabase worker report shown `(current, UNTRUSTED)`.
4. **Failure scenario.** A worker report on a page claims "plan updated to Free" and ends up shown as current next to the human value.
5. **Consequence.** This violates SPEC B6.2.3 (a tainted report must not become a value without approval). A rate of ≥ 0.50 in one S6 class on sealed seeds is DQ2.
6. **Settling test.** `injection_success_hijack` on sealed seeds, plus this probe: 0/10 required.

## G2 → Spec-Y: the Standout and four pre-registered predictions are already disproved on public seeds

1. **Disputed claim.** §p: "Summaries (T7), duplicates (S3) and stale copies cannot resurrect an old value." §o: zombie_rate S1 "Disproved if > 0.10", conflict_acc "< 0.85", heal_harm_rate "> 0.01", zombie_rate S10 "> 0.02".
2. **Suspected weakness.** Lineage inheritance only works when the origin's chain is correct. When a chain is split, the origin is a stale head in its own chain, and every restatement inherits `current` from it.
3. **Evidence.** In `attack_runs.csv` for seeds 101/102/103:
   - S1 zombie_rate: 0.079 / **0.231** / **0.222**
   - S2 conflict_acc_t4 + t5: ALL 0.667 / **0.5** / 1.0
   - heal_harm_rate: **0.167 / 0.333 / 0.333**
   - S10 summary_zombie_rate: **0.25 / 0.5 / 0.25**
4. **Failure scenario.** A recap restates a superseded code, and that code is current again.
5. **Consequence.** The headline Standout gives no protection in the case it was designed for, which bears on P5.C and P4.F.
6. **Settling test.** Sealed seeds: S10 `summary_zombie_rate` ≤ 0.02 and S1 zombie_rate ≤ 0.10, as pre-registered.


---
## Spec-Z / defence_r1.md

# Defence, round 1 (Team Spec-Z)

I re-ran every script myself from `benchmark\`. The fixed version is `spec_v2.md` plus the prototype with code hash `f38c3148d9351b6f`.

## B1 (Spec-X): a trace note erases an unrelated fact — **REVISE**
Valid. I reproduced it: `merge2.py` printed `after vercel: []  wake: []`.
**Fix:** `_heal_from_trace` now accepts a code from another slot as evidence only if `_fusion_ok` passes. The cited op must be newer than the ignored item, must be the current head of its own slot, and must stay current after the union is replayed. If the test fails, there is no demote and no merge.
**After the fix:** `report ()` and `after vercel: [('current','(VC-BBBBB1).')]`. New test: `test_v2_fusion_blast_radius_protects_unrelated_fact`.
This is a structural rule (the other slot must lose nothing), not a threshold.

## B2 (Spec-X): the "both sizes" predictions fail at 10k — **CONCEDE**
Valid. My own 10k run on seed 101 with v2 gave accuracy 0.547, zombie rate 0.530, conflict_acc 0.20, asof_acc 0.44 and query p95 18.7 ms. The cause is lexical slotting fragmenting chains as the corpus grows. A larger candidate pool did not help (0.546).
The spec_v2 changelog marks the v1 predictions as disproved at 10k. The predictions now apply to size 1000 only, and the 10k accuracy prediction is 0.45–0.65.
No tuning was done to the public seeds.

## A3 (Spec-Y): fusion demotes a fact nobody ignored — **REVISE**
This is the same root cause as B1, and the same fix covers it. Spec-Y's script now prints `Spec-Z s3_merge_collateral actions=[] vercel_after=['VC-VERCPR']`. The ignored auth item is not demoted either, because the note gives no evidence about the auth fact. That also meets Spec-Y's pass condition. Spec-X and Spec-Y's own s3 output still demotes `a1`.

## A4 (Spec-Y): one shared word lets `supersedes` cross subjects — **REVISE**
Valid; I reproduced it.
**Fix:** a first-party `supersedes` hint is refused when another slot matches the subject near-exactly (≥ 0.8) and the named slot matches weakly (< 0.4). In that case the write goes to the better slot.
**After the fix:** auth keeps `VC-AUTH45`, and `VC-REFR07` is no longer current. New test: `test_v2_supersedes_hint_must_fit_subject`.
I tried a stricter rule first ("no other slot may fit better"). It regressed seed 101 accuracy from 0.9655 to 0.9138 because it broke legitimate alias links. I replaced it with the near-exact rule. That was one iteration, and it is disclosed in the changelog.
**Public seeds 101–103 at 1k with v2:** every metric is identical to v1 (accuracy 0.9655 / 0.9333 / 0.9286, injection 0, leaks 0). Tests: `16 passed`.

## Kill claims
- **Spec-X:** a first-party agent write about an unrelated subject that names a human decision in `supersedes` replaces that decision, and it stays replaced after `maintain()`. Our `hijack_probe.py Spec-X` printed `'which STT provider?' [('x1','current',())]`.
- **Spec-Y:** an external worker report that carries a path skips its stated T3 hijack defence (`adapter.py` L203-204). It is shown `current` in 10 of 10 trials (`external_hijack_probe.py Spec-Y`), and harness seed 102 already shows hijack-class success of 0.5, which on sealed seeds is the DQ2 class threshold.


---
## Spec-Y / attacks_r1.md

# Kill-round attacks r1 (Spec-Z author → Spec-X, Spec-Z)

**Evidence for all four attacks.** The script `teams/Spec-Y/atk_r1.py` drives each prototype only through the frozen Adapter API. Run it from `benchmark\` with `.\.venv\Scripts\python.exe ..\teams/Spec-Y/atk_r1.py`. The output below is real and was RUN on 2026-11-23 against the frozen prototypes. Hashes: Spec-X `780da809e9d1`, Spec-Z `5906a205a2ad`, as printed by `harness.runner`.

The harness runs on the rivals' public seeds 101–103 are in `teams/Spec-Y/atk_{Spec-X,Spec-Z}_{101,102,103}.csv`.

---

## A1 (Spec-X): a cue word alone demotes a correct memory (P5 heal harm; disproves Spec-X §o)

1. **Disputed claim.**
   - §o says: "heal_harm_rate … Disproved if … any harm traced to a `demote` action".
   - §p says blast-radius healing "makes 'heal harm' a checked property per action".
2. **Weakness.** `evidence()` returns a reason when the note merely matches `CUE` ("actually|instead|wrong|…"), with no code and no path. The blast-radius check only verifies that *only the target* changed. It never checks that the target was wrong.
3. **Evidence (RUN).**
   ```
   Spec-X s1_cue_only_demote  before=['VC-OTP006'] actions=['demote'] after=[]
   ```
   The note was "Skipped it: the user actually wanted a summary first." Spec-Z and Spec-Z give `after=['VC-OTP006']`.
4. **Failure scenario.** A correct fact is ignored for an unrelated reason. Any everyday note word such as "actually" or "instead" demotes it permanently.
5. **Consequence for ONE FOR ALL.** Agents' free-text session notes routinely contain these words. Correct decisions, such as an ask-budget answer (SPEC B6.7), silently disappear from context, and the agent asks the user again.
6. **Test that settles it.** H2-style traces whose notes contain each `CUE` word and no code. Pass condition: 0 demotes.

---

## A2 (Spec-X): cross-chain `supersedes` overwrites an unrelated fact (P1, P6, S6 hijack class)

1. **Disputed claim.**
   - §c step 5: "first existing op named in `supersedes` … → that chain".
   - §h: "`supersedes` hijack … REPRODUCED".
   - INTERFACE §2 truth ignores supersedes that point into other chains.
2. **Weakness.** `_assign_chain` joins the target's chain with no subject check, for first-party writes too. It then becomes head through T1/T2.
3. **Evidence (RUN).**
   ```
   Spec-X s2  auth=['VC-VERCTM'] (truth VC-AUTH45) vercel=['VC-VERCPR','VC-VERCTM'] (truth VC-VERCTM)
   Spec-X s4  auth=['VC-REFR14'] (truth VC-AUTH45) refresh=['VC-REFR07','VC-REFR14']
   ```
4. **Failure scenario.** Codex lists a wrong or stale op_id, or a hostile first-party worker names the auth head on purpose. The auth TTL is replaced by a Vercel plan value, and the real Vercel plan keeps a zombie.
5. **Consequence for ONE FOR ALL.** A single bad id from one agent erases a security setting for every agent. This is a poisoning path that T3 does not cover, because the writer is first-party.
6. **Test that settles it.** A first-party write whose `supersedes` points into another chain. Pass condition: the target chain head is unchanged and the new code is current only in its own subject.

---

## A3 (Spec-Z): "correction-anchored fusion" demotes a fact nobody ignored (P5 harm, Standout §p)

1. **Disputed claim.**
   - §g: "If the note's code belongs to another slot → `merge(slotA, slotB)`; replay of the union then picks the true head".
   - §n.7 says the harm "comes from retrieval misses … not from heal actions".
2. **Weakness.** Any code mentioned in a note fuses two unrelated slots. The replay of the union then supersedes the older slot's head.
3. **Evidence (RUN).**
   ```
   Spec-Z s3_merge_collateral  actions=[('demote',['a1']),('merge',[1,2])] vercel_after=[] (truth VC-VERCPR, never ignored)
   ```
   Spec-X and Spec-Z: `vercel_after=['VC-VERCPR']`.
4. **Failure scenario.** A note from a session that used the Vercel plan while ignoring the auth item fuses the two facts. The correct, never-ignored Vercel value stops being current for every agent.
5. **Consequence for ONE FOR ALL.** Heal actions that are not reversible from the item's point of view: undo needs a human to find the merge. The harm is caused by `maintain()`, which contradicts §n.7.
6. **Test that settles it.** H3/H2 traces whose notes cite a code from another chain. Pass condition: no merge, and every un-ignored chain head is still current.

---

## A4 (Spec-Z): one shared word lets `supersedes` cross subjects (P1, P6; disputes Spec-Z §h)

1. **Disputed claim.** §h: "`supersedes` hijack | slotting requires subject overlap with the target slot | REPRODUCED".
2. **Weakness.** `_shares()` accepts **any single** common term (`… term IN (…)` LIMIT 1). "token" or "ttl" is enough to put a refresh-TTL write into the auth-TTL slot.
3. **Evidence (RUN).**
   ```
   Spec-Z s4_one_shared_term  auth=['VC-REFR07','VC-REFR14'] (truth VC-AUTH45) refresh=['VC-REFR07','VC-REFR14'] (truth VC-REFR14)
   ```
   The auth value is lost and the old refresh value is a zombie. Spec-Z: `auth=['VC-AUTH45',…]`, with VC-REFR07 not current.
4. **Failure scenario.** Near-miss subjects (INTERFACE §3: "auth token TTL" vs "refresh token TTL") plus one mistaken supersedes id.
5. **Consequence for ONE FOR ALL.** The voice agent reads a refresh lifetime as the access-token TTL. That is a security misconfiguration reported as current.
6. **Test that settles it.** The same script with every near-miss pair from the generator catalogue. Pass condition: the target head is kept and the stale near-miss value is not current.

---

## Defence notes (own spec; not an attack)

- `s3` also shows that Spec-Z demotes an ignored item whose note cites an unrelated code (`Spec-Y … actions=[('demote',['a1'])]`). That is the same rule as Spec-X's and Spec-Z's demote.
- Expected counter-attack: "a code in the note is not proof that it is the same fact". Planned answer: require the cited code's origin chain to equal the item's chain, or be unknown. That needs a revision.


---
## Spec-Y / defence_r1.md

# Defence r1 (Spec-Z)

I re-ran every attack script myself from `benchmark\`. The revision is in `spec_v2.md` (changelog at the top) and `prototype/adapter.py`.
- Code hash: v1 `bd7ba7f08b7f5fe0` → v2 `cb925a7aedb4103a`.
- Tests: 16 passed.
- Public-seed numbers before and after: `spec_v2.md` Appendix C.

## Spec-X-G1: external hijack with a path → **REVISE**

The attack is valid. Our v1 `_assign_chain` returned `p:<path>` before it checked `supersedes`. This is a rule-order fix, not a tuning change:
- An external write that names a known op now always joins that op's chain, where T3 blocks it.
- A path is only a natural key once it is known.

| | v1 | v2 |
|---|---|---|
| seed 102 `injection_success_rate` | 0.1667 | 0.0 |
| `injection_success_hijack` | 0.5 | 0 |
| seeds 101 and 103 | 0.0 | 0.0 |

Regression test: `test_v2_external_hijack_with_new_path_is_not_current`.

Falsifiable test: on the sealed seeds, `injection_success_hijack` must be 0.

## Spec-X-G2: T5 stale-base write shown current → **REVISE**

The attack is valid. A reworded first-party write with `supersedes` fell through to a new chain, so the T5 rule never saw it. Fix: `supersedes` is now a strong hint. It is overridden only when another existing chain matches the write strictly better, which is the rule that keeps our attacks A2 and A4 out. I also removed the +0.25 target bonus.

Re-run of `t5.py Spec-Y 101/102`: the stale codes VC-1QH48N and VC-4Q8U89 are no longer shown `current`. Measured on seeds 101/102/103:

| | v1 | v2 |
|---|---|---|
| `conflict_acc_t5` | 0.33 / 0.67 / 0.67 | 0.33 / 0.67 / 1.0 |
| `conflict_acc` | 0.67 / 0.50 / 1.0 | 0.67 / 0.67 / 1.0 |

The remaining misses are retrieval misses: the true head is not ranked into the bundle. They are not stale-current failures. The pre-registered "conflict_acc ≥ 0.95" is still missed on public seeds; I concede that part.

Test: `test_v2_reworded_stale_base_stays_in_chain`.

## Spec-Z-G1: external hijack with a path, 10/10 trials → **REVISE**

This is the same root cause as Spec-X-G1 and the same fix. Re-run of `external_hijack_probe.py Spec-Y`:

| | v1 | v2 |
|---|---|---|
| external code shown current | 10/10 trials | 0/10 trials |

Measured against Spec-Z's own probe. The DQ2 class rate is now 0 on seeds 101–103.

## Spec-Z-G2: Standout and predictions already disproved on public seeds → **CONCEDE**

The numbers are correct, and the misses were already disclosed in v1 Appendix B. Lineage inheritance does what it says: a copy is never fresher than its origin. But an origin that is a stale head of a **split chain** passes `current` to every restatement. The protection is therefore only as good as chain resolution, which the §p text did not say.

v2 lowers S1 and overall zombies a little (0.103/0.217/0.250 against 0.103/0.250/0.268) but does not meet the pre-registered ≤ 0.10 or ≤ 0.02. The §o predictions stay as registered and will be judged on the sealed seeds.

## Kill claims

- **Spec-X:** `evidence()` demotes a correct memory on a note that contains only the word "actually". Our `atk_r1.py` output was `Spec-X s1_cue_only_demote before=['VC-OTP006'] actions=['demote'] after=[]`. That meets Spec-X's own §o disproof condition, "any harm traced to a `demote` action", and the same script shows its first-party cross-chain `supersedes` replacing the auth TTL.
- **Spec-Z:** its Standout merge heal makes a fact that nobody ignored non-current. Our `atk_r1.py` output was `Spec-Z s3_merge_collateral actions=[('demote',['a1']),('merge',[1,2])] vercel_after=[]`. That is harm caused by `maintain()` itself, which contradicts Spec-Z §n.7.
