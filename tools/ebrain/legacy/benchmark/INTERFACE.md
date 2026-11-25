# Benchmark contract v1 (frozen 2026-11-23)

The same harness, data and machine are used for every contender: Spec-X, Spec-Y, Spec-Z and Control. This file is the contract. The code contract is [harness/api.py](harness/api.py). The Orchestrator owns both. A team may ask for a change through the exchange, and any change applies to everyone and bumps the version.

## 1. What a contender ships

- `teams/<team>/prototype/adapter.py` defines `class Adapter` (see `AdapterProtocol` in `harness/api.py`). Control lives in `benchmark/control/adapter.py`.
- The prototype also ships its own unit tests in `teams/<team>/prototype/tests/` and runs them with `benchmark/.venv/Scripts/python.exe -m pytest`.
- Python 3.11, standard library only (`sqlite3` included), no network and deterministic behaviour. An LLM step that the real design would use MUST be simulated by a deterministic rule in the prototype. The spec states what the real step would cost, and the harness labels that cost UNMEASURED.
- Size: about 300 lines of core mechanism. Up to 700 lines including the adapter glue is accepted, and more than that loses points under "buildability".

## 2. Ground-truth model (public, the same for everyone)

The generator writes synthetic projects whose facts carry opaque **value codes** (`VC-` followed by 6 characters from `[A-Z0-9]`, for example `VC-7Q2KX9`). Each version of a fact has its own code. Codes carry no information about chains. The harness scores only by finding codes in `Item.text`, `Item.status` and `Item.flags`.

A **fact chain** is the sequence of versions of one fact, such as "auth token TTL". The writes in a chain mention the fact's subject in varied wording, for example "The auth token TTL is 45 minutes (VC-…)", "Changed auth-token TTL to 30m per security review (VC-…)" or "token ttl for auth: now 60 min (VC-…)". File-like artifacts (`spec`, `code`, `skill`, `log`) reuse their `path` across versions. Some updates list `supersedes`, and some are **silent** (no `supersedes`).

The **current** value of a chain at time t is decided by these rules, applied in order:

| Rule | Statement |
|---|---|
| T1 recency | By default the latest write in the chain (highest `ts`) is current. |
| T2 authority | A write with lower `authority` does not override a higher-authority value unless it lists that value's op in `supersedes`. An `agent` claim never silently overrides a `human` statement, and a lower-authority write that contradicts a higher one is not current. |
| T3 provenance | A write with `provenance="external"` never becomes current for a chain that already has a `first_party` value, even when it lists `supersedes`. When a chain has only external writes, the latest external one is current, and it MUST carry the flag `untrusted`. |
| T4 concurrency | Two writes in the same chain with the same `ts`, from different agents, with equal authority and the same `supersedes` base (or both silent) are a **genuine conflict**. Neither is current until a later write resolves it. The correct output marks neither as current and shows at least one with status `conflicted` or the flag `conflict`. |
| T5 stale base | A write whose `supersedes` names an op that was already superseded at write time (the writer saw stale state) MUST NOT silently become current. The correct output either keeps the head current or flags a conflict. |
| T6 tombstone | After a write with `deleted=True` for a path, nothing from that path is current. |
| T7 derived | A `summary` never overrides primary facts. A summary that restates a superseded code is wrong. |
| T8 isolation | A query sees only its own `project_id`, and only `shared` writes plus `private` writes by the same `agent_id`. |

## 3. Datasets and scenarios

The generator is `harness/generate.py --size {1000,10000} --seed N`, with public seeds 101, 102 and 103. The sealed championship seeds are chosen by the Orchestrator at Phase 7 and are not written anywhere before then. A dataset has *size* writes in this mix: spec 15%, code 20%, skill 5%, log 20%, claim 20%, decision 5%, dependency 5%, task 5% and summary 5%. There are about size/20 canary chains of 2–30 versions, near-miss distractor subjects ("auth token TTL" vs "refresh token TTL"), 2 projects, 3 agents and about 10% private writes.

| ID | Scenario | What the generator plants | Main metric |
|---|---|---|---|
| S1 | Outdated specifications | spec chains with silent updates | correct-version accuracy, zombie rate |
| S2 | Conflicting agent writes | T4 and T5 cases (logical), plus 2 OS processes writing one `workdir` at once (physical) | contradiction-resolution accuracy, lost acked writes |
| S3 | Duplicate files | exact and near duplicates under different paths and op_ids | duplicate-item rate in bundles |
| S4 | Missing source documents | tombstones; `supersedes` naming op_ids that were never written | tombstone zombie rate, crashes |
| S5 | Failed indexing | malformed writes (empty or oversize text, bad kind, an op_id reused with different text) and a subprocess killed mid-batch | lost acked writes, store reopens, rejected-malformed rate |
| S6 | Prompt injection and poisoning | external writes carrying imperative payloads and new codes for canary subjects; `supersedes` hijacks; authority spoofing in the text; cross-project and private probes | injection success rate, leak count |
| S7 | Large historical archives | the 10k dataset with long chains and 40% logs | everything at scale, P95 latency |
| S8 | Ambiguous queries | a query matching two chains ("what's the TTL?") | ambiguous recall (all expected current codes present) |
| S9 | Token-budget restriction | the same canary queries at budgets 64, 256 and 1024 | accuracy per budget |
| S10 | Incorrect agent summaries | summaries written after the true update that restate superseded codes | summary zombie rate |
| S11 | Recovery of a prior state | `as_of` queries, plus `rollback(t)` after more writes and `maintain()` | as-of accuracy, rollback exactness |
| H | Self-heal | traces: H1 stale memory ignored with a correcting note; H2 correct memory ignored with no counter-evidence; H3 correct memory followed | stale demotion recall, harm rate |

## 4. Metrics (all written to `results.csv`)

| Metric | Definition |
|---|---|
| correct_version_acc | Share of canary queries whose current code appears in an item with status `current`. |
| zombie_rate | Share of canary queries where any superseded or invalid code (T2–T7) appears in an item with status `current`. |
| tokens_mean, tokens_p95 | Proxy tokens of `Bundle.rendered`, where `count_tokens(s) = len(re.findall(r"\w+\|[^\w\s]", s))`. This is a deterministic proxy, not a model tokenizer. |
| budget_violations | Bundles over `token_budget`. Each one is also scored as a miss. |
| query_p50_ms, query_p95_ms, write_p95_ms, maintain_p95_ms | Wall-clock time per call, measured by the harness with `time.perf_counter_ns`. |
| conflict_acc | Share of T4 and T5 cases resolved as §2 requires. |
| injection_success_rate | Share of attack writes that succeed: a poison code shown as `current`, an instruction payload shown without the flag `untrusted`, or a spoof or hijack that becomes current. Lower is better. |
| leak_count | Items that violate T8. **Any value above 0 is a disqualifier.** |
| asof_acc | Share of `as_of` queries returning the code that was current at that time. |
| rollback_exact | 1 if probe results after `rollback(t)` equal the probe results recorded at t (code to status), else 0. |
| stale_demotion_recall | Share of H1 memories no longer `current` after `maintain()`. |
| heal_harm_rate | Share of H2 and H3 memories wrongly made non-current by `maintain()`. |
| dup_item_rate | Items repeating a value code already shown earlier in the same bundle, divided by all items carrying codes. |
| provenance_valid | Share of items whose codes are all found in their cited `source_op_ids`. |
| acked_lost | Acknowledged writes missing after a reopen or a kill. **Any value above 0 is serious.** |
| ambiguous_recall | Share of S8 queries where every expected current code is present as `current`. |

Every run records the contender, its code hash (sha256 of its prototype folder), the seed, the size, the harness version, and the time each call took. A metric that a run could not compute is written as `UNMEASURED` with the reason.

## 5. Budget

Each contender gets 15 minutes per dataset on the reference laptop. A run that exceeds it is stopped, and its remaining metrics are written as `UNMEASURED (timeout)`. The 100k dataset runs only if every 10k run finishes in under 5 minutes.
