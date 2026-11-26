# Milestone acceptance cases (consolidated)

Single index of every milestone acceptance matrix for the V3 implementation plan.
Consolidated 2026-11-26 from the eight per-milestone `TEST_CASES.md` files; all
rows and surrounding notes are preserved verbatim. This is planning/acceptance
documentation only — no test code, contract, schema or evidence was changed.
The authoritative finding-to-test mapping remains [TRACEABILITY.csv](TRACEABILITY.csv).

## Index

| Milestone | Section |
| --- | --- |
| M7 — evaluation and contracts | [M7 cases](#m7--evaluation-and-contracts) |
| M8 — ledger and security | [M8 cases](#m8--ledger-and-security) |
| M9 — fact identity and filing | [M9 cases](#m9--fact-identity-and-filing) |
| M10 — retrieval | [M10 cases](#m10--retrieval) |
| M11 — resolver and decisions | [M11 cases](#m11--resolver-and-decisions) |
| M12 — projections and maintenance | [M12 cases](#m12--projections-and-maintenance) |
| M13 — team security and operations | [M13 cases](#m13--team-security-and-operations) |
| M14 — tiers, UI, migration and release | [M14 cases](#m14--tiers-ui-migration-and-release) |

## M7 — evaluation and contracts

All are planned; none is claimed executed by the planning task. Use synthetic data and keep labels outside implementation inputs.

| ID | Setup / stimulus | Must observe |
| --- | --- | --- |
| H05 | Return true current plus one superseded current; then empty for every query | Joint exact fails both answerable cases; zombie detected; no accuracy from empty response. |
| M01 | Schema-1 client, schema-3 client, unknown schema, timed-out committed retry | Compatibility explicit; same idempotency receipt; unknown schema rejected; errors machine readable. |
| M04-generator | Generate 100k events and separately 100k distinct keys with varied revisions | Manifest counts match actual unique qualified keys/events; repeated seed hash stable; no exhaustion. |
| EV-ORACLE | Reviewed sequential, conflict, late, future, erased and scoped histories | Oracle expected states/cuts validated without product imports. |
| EV-LABELS | Scan model/index/request fixtures, caches and adapter inputs | Hidden oracle identifiers/ground-truth codes absent except declared legitimate selectors. |
| EV-SEALED | Simulate sealed reveal followed by tuning | Manifest retired; new independent suite required before release evidence accepted. |
| EV-DENOM | Pending/unassigned write, partial multi-fact query, clipped conflict | Filing miss/pending counted; incomplete answer fails complete gate; delivered metrics match bytes. |
| EV-RUNTIME | Reference and product contender in separate clean subprocesses | Expected module file paths + combined adapter/product digests recorded; no cached reference import. |

Checkpoint record template: ID, source digest, test node IDs, command/cwd, fixture/protocol hash, run manifest, PASS/FAIL/NOT_RUN, failure notes, reviewer.

## M8 — ledger and security

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C03 | Kill worker immediately after committed write; query exact and text with/without receipt | Authoritative transition/pending, never stale current; resume converges; no lost ack. |
| C04-foundation | Same IDs in two orgs; foreign scope FKs; runtime-role joins/upserts; pooled context reuse | No cross-scope row/identifier/count; FK/RLS fail closed; context cleared. |
| C05-foundation | Server recorded cut with delayed/future client clock | Knowledge order follows commits; valid interval retained; unknown time explicit. |
| C06-foundation | Barrier-sync same key retries and conflicting request digests; concurrent last reservation | One semantic event/key, digest mismatch 409, transactional quota; no partial event/job. |
| C07 | Synthetic secret in nested/encoded/malformed/oversized/compressed inputs; scanner down | Rejected/redacted before DB/object/log/job/model; quarantine bounded and not searchable. |
| LEDGER-FAULT | Timeout after commit, rollback before commit, crash after object staging, duplicate job | Same-key receipt recovery; no false ack; orphan cleanup; idempotent application. |
| FENCE-ELIGIBILITY | External/unauthorized agent mentions higher-authority fact; authorized ambiguous update | First cannot force human current unavailable; latter fences eligible impact until adjudicated. |
| SNAPSHOT-AUTH | Revoke permission during query; min_seq ahead of replica | Retry/deny before delivery; primary or pending, never stale authorized cache. |
| QUOTA-BASE | Concurrent bounded pending/event admissions and exact retries | Counters/reservations atomic; no accepted content silently expires. |

Record restricted database role, schema/policy hash, fault point, committed seqs, acknowledgments and recovered rows. Test missing prerequisites explicitly; do not silently substitute SQLite.

## M9 — fact identity and filing

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C02 | Access vs refresh, prod vs stage, branch/ref/repo, intended vs observed, same path across org/project | Separate canonical facts; unknown qualifier never matches prod. Exact approved alias joins only compatible key. |
| C08-identity | Consistently wrong classifier result over multiple rebuilds | No automatic approved equivalence; independent labelled audit catches false identity; source ledger remains recoverable. |
| H02 | OOD jargon, same unit/different target, near-miss, missing qualifier, forged model IDs | Validated pending/review; no high score auto-merge; report coverage/calibration. |
| M06-source | Same scalar on unrelated line, negation, unit conversion, mutable source revision | Exact sanitized span/digest and semantic support validated; unsupported field stays unverified. |
| M10 | Replay source, rename branch/path, partial scan, removed source, permission failure | Dedup by stable revision, no false deletion; explicit confirmed status event; correct freshness dependency. |
| ID-LINEAGE | Authorized lineage disagrees with path or references multiple facts/foreign target | Explicit rejection/review; no first-target/fuzzy selection; no existence disclosure. |
| ID-SPLIT | Reviewed mixed legacy chain split with pending ambiguous claim | Each eligible claim maps to one fact; unknown remains pending; old identity cut reproducible. |
| ID-CONCURRENT | Simultaneous register same canonical key | One fact; receipts/bindings idempotent; no double quota charge. |

Trace source spans, identity events, generation, proposal digest, reviewer and before/after resolver preview for each identity mutation.

## M10 — retrieval

| ID | Stimulus | Expected result |
| --- | --- | --- |
| H01 | Exact old code, shared path across repos, near-tie, multi-fact query, malicious reranker truncation | Protected qualified facts preserved; historical code stays historical; missing facet triggers widen/partial. |
| H03 | Same vector dimension/new weights, changed tokenizer, interrupted backfill, rollback | No mixed generation comparisons; coherent pinned active generation and catch-up. |
| H10 | Model/vector/index/replica/DB failure, cancellation and deadline | Declared degradation/partial/pending/unavailable; exact proven states remain safe; no stale current fallback. |
| C03-search | New exact claim committed while search generation lags | Exact/delta overlay or pending fence; min_seq honored without waiting indefinitely for model. |
| C04-search | Restricted fact through ANN, graph neighbors, lexical stats, autocomplete, count and cached query | No unauthorized content/ID/existence; scope narrowing cannot add hidden results. |
| RET-RRF | Absent arm and duplicated candidate with weighted ranks | Correct declared RRF, stable tie handling and provenance; protected union survives. |
| RET-BUDGET | Tight compact budget with conflict/status/source requirements | Critical state retained; omitted facets labelled partial; actual delivered metrics fail if incomplete. |
| RET-ANN | Exact filtered baseline vs ANN under skewed scopes/restrictive filter | Measured recall/latency; fallback before accepting insufficient coverage. |

Save candidate IDs only in authorized restricted evidence; public/general telemetry contains no raw query, hidden IDs or vector payload.

## M11 — resolver and decisions

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C01 | Agent forges human role/approval and references human head; valid bounded delegate then writes | Forgery never changes current or creates denial-conflict; delegate succeeds only within granted predicate/scope/time. |
| C05 | Late observation, future decision, retro-correction, equal server times, old identity/policy cut | Correct valid/knowledge semantics, scheduled state, no backdated knowledge; current auth on every cut. |
| C06 | Barrier-synchronized competing writes with shared base, unequal clocks; known stale-base request | First cut valid; second eligible branch conflict/no current; stale attempt rejected/noncurrent. |
| C09 | Edit target after proposal; revoke reviewer; duplicate/concurrent approval; cross-scope promotion | Exact digest/CAS/permission enforced; no stale, self or double action. |
| C10-logical | Tombstone then old-state rollback; legitimate restore; erased target; multi-fact failure | No implicit resurrection/erased bytes; explicit new decision; full history; no hidden partial batch. |
| H09 | Intended TTL 30m, observed prod 60m, expired source, source revision retracted | Separate intended/observed answers; stale observation unknown; decision validity follows contract. |
| M03 | Missing steward, overdue critical proposal, duplicates | Authorized escalation/dedup/cap; stays pending without auto-approval. |
| M08 | Before/after approved policy activation; unsafe production config toggle | Correct historical replay; unsafe toggle refused; manifest activation audit. |
| RES-PROPERTY | Same admitted ledger under worker batches/rebuild, unrelated fact insertion, equivalent units | Canonical exact result unchanged; one scalar current; independent replay agrees. |

Explicitly retain evidence showing low authority cannot gain permission from lineage, unlike the legacy benchmark’s T2 rule. A successful old benchmark is not approval for that V3 behavior.

## M12 — projections and maintenance

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C08 | Corrupt card current/cache/binding; rebuild same wrong classifier mapping | Projection cannot override ledger; digest divergence fenced; independent semantic audit catches stable wrong identity. |
| H04 | Repeated hallucinated summaries, cyclic citations, automatic re-ingestion | Derived-only namespace, cycle/depth reject, no independent corroboration/current; reviewed separate decision required. |
| M05 | Negation, historical change, different subject, unit mismatch, repeated noisy NLI | Typed overlap gate; advisory issue only, dedup; precision/recall measured, no automatic resolution. |
| M06 | Span digest mismatch, changed/erased source, unsupported prose with same number | Invalid support unavailable/pending; claims cannot gain current from string presence. |
| M08-projection | Semantic manifest change mid rebuild and rollback | Coherent pinned cut/generation, approved activation and reproducible history. |
| M09-assembly | Clip conflict/evidence, omit transport ack, fabricated “agent used” claim | Status preserved/partial; sent vs acknowledged vs reported distinct; unknown stays unknown. |
| PROJ-FAULT | Worker duplicate, interrupted shadow build and active-generation corruption | Idempotent catch-up, no partial pointer activation, safe replay fallback. |
| MAINT-HARM | Correct evidence ignored by agent vs genuinely superseded evidence | Feedback alone changes no authority/state; per-action proposed harm/review recorded. |

Evaluate both canonical state and actual assembled content; a clean card digest cannot excuse an invented natural-language answer.

## M13 — team security and operations

| ID | Stimulus | Expected result |
| --- | --- | --- |
| C04 | Full two-org/hidden-project reuse, revoked session, ANN/graph/cache/cursor/receipt/export/backup path | Zero unauthorized content/ID/existence disclosures; final grant epoch check; runtime-role proof. |
| C07-erase | Synthetic secret discovered post-admission; erase and restore older backup | Immediate suppression, verified removal across controlled stores; latest suppression before any serving. |
| C10-recovery | Old backup contains revoked grants/erased source; missing suppression authority | No restored access/content; fail closed if latest authority unverified; accepted events reconciled. |
| H08 | Indirect Unicode/encoded injection in repo/tool/model content, forged metadata/MCP request | No unauthorized write/tool/network/disclosure; typed output and original principal scope enforced. |
| H10-ops | DB failover, queue storm, disk full, auth/scanner outage, model down | Explicit backpressure/failure contract; no false ack/stale current; security failures closed. |
| M02 | Inject lag, leak canary, review overdue and failed backup | Safe diagnosis/alert/runbook ownership; no raw content/token telemetry. |
| M03-team | Steward deprovision, self-approved promotion, missing second reviewer | Reassign/escalate/block, never auto-approve. |
| M04 | 200 sessions, separately concurrent request saturation, 100k facts with hot revisions | Declared hardware/workload and correctness/recall/tail/resource results, honest limits. |
| M09 | Truncated transport/no ack, forged use feedback, revoked receipt viewer | Generated/sent/ack/reported separated; unknown preserved; unauthorized feedback/read refused. |
| CLIENT-VOICE | Overlapping queries/scopes, delayed refresh, revoke and expired pack | Older worker cannot overwrite newer valid scope; stale/unverified memory not asserted current; voice nonblocking. |
| CLIENT-AGENT | Real authorized Claude/Codex sessions and Stop fallback/flush sequence | Actual load/capture evidence, idempotency/scope and privacy; delivery not proof of use. |

Security test output must be sanitized; only synthetic secrets can be fixtures. A reported zero count is scoped to the executed threat suite, never a proof of zero production risk.

## M14 — tiers, UI, migration and release

| ID | Stimulus | Expected result |
| --- | --- | --- |
| H06 | Concurrent legacy writes during export, duplicate ID namespace, unknown time, interrupted cutover, new V3 writes before rollback | Every accepted source event mapped/reconciled or explicitly quarantined; one writer; post-cutover writes never lost; forward repair if reverse unsupported. |
| H07 | Last-slot concurrent new facts, retry storm, unassigned flood, revision spam, merge/split/retire | Atomic reservations/settlement; separate event/history budgets; explicit backpressure; authorized corrections remain possible. |
| M01 | Every supported client/version, scoped cursor under revocation, malformed pending/error, timed-out replay | Explicit schemas/errors, no unsafe flattening, same receipt/no duplicate, current grants on each page. |
| M07 | Pending/conflict/partial/stale/unknown and intended vs observed; narrow-permission reviewer | No false current; distinct confidence/freshness/completeness; absent hidden detail; accessible approved workflow. |
| M08-release | Unapproved semantic flip or edited measured facts | Activation denied/generation mismatch detected; source measurements unchanged without reproducible generation. |
| RELEASE-FACTS | Regenerate API/web facts using final raw results and manifests | Identical generated artifacts, no targets/unrun values claimed measured, old metric/catalogue labelled. |
| RELEASE-SEALED | Independently controlled seeds, failed required stratum/timeout, tuned sealed retry | Failure preserved; no selective seed average or same “sealed” tuning; final manifest trusted. |
| RELEASE-LIVE | Real browser/API, authorized coding/voice clients, labelled engineering pilot | Live behavior demonstrated separately from mocks; sanitized evidence and owner sign-off; no personal data bootstrap. |

All 30 C/H/M findings remain release requirements through their primary milestones. This table does not replace TRACEABILITY.csv or the full V3 checklist.
