# Proposed ADR drafts — M7 (D01, D02, D03, D09)

Status: **DRAFT / NOT APPROVED**. These are reviewable proposals only. Nothing
here activates a V3 product change, a model call, a migration or an external
service. Do not append them to `DECISIONS_LOG.md` until the owner approves
them; the log and all status/checkpoint files remain unchanged by M7.

---

## D01 — Postgres V3 transaction boundary, schema-3 negotiation and single-writer migration

**Old rule (schema 1 / experimental service).** SQLite store; `accepted=false`
is a valid successful write response; an unrecognized request field is
silently treated as a legacy request; no explicit schema negotiation.

**Proposed new rule.** A separate V3 implementation on isolated Postgres:

* `write` is committed inside one database transaction with the durable
  receipt and outbox row. `201` = `applied|accepted_noncurrent|conflict`,
  `202` = `accepted_pending`, `200` = authorized idempotent replay.
  `accepted=false` as a success response exists only in schema 1.
* Wire negotiation is explicit: `X-EBrain-Schema: 3`. Schema `1` resolves to
  the legacy surface; an unknown value is rejected `400` with the
  machine-readable error body `{code,message,request_id,retryable}` and never
  inferred from an unexpected field. See
  `docs/ebrain/contracts/v3/negotiation.schema.json` and
  `compatibility_matrix.fixture.json`.
* Migration runs with one writer, a freeze/final-delta rehearsal and a
  forward repair path; legacy remains usable and frozen CSVs are untouched.

**Example.** A timed-out `write` retried with the same `idempotency_key` and
digest returns the original receipt (`committed_seq`, `replay_marker`); it
must not mint a second write.

**Impact / evidence.** Requires M8 transaction and receipt tables; M7 provides
strict write/ack/receipt schemas and fixtures plus `query`/`answer` schemas.
Activation requires owner approval; rollback disables the V3 routes and keeps
schema 1 available. `EV-RUNTIME` records separate module digests so a cached
reference store can never stand in for the product store.

---

## D02 — Replace ADR-2 "no model / no embeddings" only for explicitly scoped local accelerators

**Old rule.** ADR-2 bans models and embeddings; no local encoder or reranker
is permitted in the resolver path.

**Proposed new rule.** Keep the ban for the resolver and for any external
fallback, but allow explicitly scoped local accelerators:

* filing suggestions may run **asynchronously** and are never authoritative;
* an approved local query encoder and reranker may propose candidates with a
  pinned artifact manifest (runtime, checksum, calibration, hardware);
* the resolver stays model-free and deterministic; no external egress;
* retrieval recall is reported per arm and before/after rerank with the same
  denominators.

**Example.** A local encoder proposes ten candidates; the authoritative exact
answer still comes from the resolver at the pinned snapshot. If the encoder
is absent, the answer degrades explicitly (`degradation.omitted_facets`) and
never becomes a silent "current" flattening.

**Impact / evidence.** Blocks M9/M10 model activation until D07 pins the exact
artifacts. M7 contracts carry `snapshot.model_generation` and
`retrieval_generation` as explicit, nullable fields; no model is installed or
called here. Rejection keeps the current no-model rule unchanged.

---

## D03 — Authority, delegation, source assertion and conflict rules (including legacy T2/T3 change)

**Old rule.** Frozen legacy harness T2/T3 lets higher-authority writes and
external versions alter the "current" value under its own truth rules; the
legacy spec is frozen and must not be edited to match V3.

**Proposed new rule.**

* Server-authorized, domain-scoped grants replace inferred authority:
  lineage is evidence, never permission. `source.contract`, `principal` and
  `grant` are required in the write schema.
* Intended (`valid_from`/`valid_to`) and observed (`knowledge_seq`,
  `observed_seq`) time are distinct; recorded time is server assigned.
* A source proves an assertion was made, not that it is true. Derived,
  recommendation and external evidence cannot establish a scalar current.
* Two equal-authority assertions at the same cut with the same base and
  different sources yield `state=conflict` and no scalar current until a
  reviewed decision resolves it.
* Legacy T2/T3 is **not** used to force V3 to permit lower-authority or
  external-current overrides. Compatible scenarios are compared directly;
  changed-semantics cases are published separately.

**Example.** Two agents assert different values at the same `ts` from the same
base. The answer reports both as `conflict`, `value=null`; it does not pick
the lexically later one. See `answer.fixture.json` and the independently
reviewed `miniature_history.json` (`K/CONFLICT`).

**Impact / evidence.** Blocks M11 semantic activation and M8 contract
boundary. M7 oracle implements these rules independently of product code and
the negative controls prove that a "true + zombie" answer is rejected. The
frozen harness and historical CSVs remain byte-unchanged.

---

## D09 — SLO/evaluation protocol and independent sealed evaluator

**Old rule.** Legacy tournament seeds/scores used incompatible truth rules and
a disclosed championship set; averages could hide a bad seed, and dataset
construction was sometimes reported as an accuracy result.

**Proposed new rule.**

* Retain the V3 thresholds in `protocol.json` (joint exact and legacy presence
  each >= .95, zombie <= .05, filing >= .98, protected-recall >= .99,
  conflict >= .90, broad temporal >= .95, abstention bounds) and record the
  hardware boundary, every failed seed/stratum and all denominators.
* Public seeds 101/102/103 are development only. Old disclosed seeds are no
  longer secret. An independent evaluator owns a new sealed seed/fact-family/
  template/repo manifest; the implementer sees only a commitment hash until
  final evaluation.
* Tuning on a sealed failure **retires** that suite; release evidence requires
  a new independent suite (`manifest.retire_suite` / `check_suite`).
* Cache keys are sanitized inputs + scope + full manifest, never labels. Live
  models run separately from deterministic recorded replay. A job omitted for
  missing secrets is NOT_RUN, never a green release gate.
* JOINT EXACT is primary; legacy presence is diagnostic and cannot compensate.
  Pending/unassigned writes count as filing misses; clipped facets fail the
  complete gate; delivered bytes are checked against the reported count.

**Example.** A contender with joint exact .96 on seed 101 but .91 on seed 103
fails the gate; no average waives a bad seed. A retired sealed suite cannot be
reused by revealing its payload and recomputing the same commitment.

**Impact / evidence.** M7 ships the versioned CLI, protocol hash, generator,
independent oracle, negative controls and sanitized evidence manifests. M13
supplies load/latency and live-model proof; sealed evaluation remains
NOT_CONFIGURED until an independent owner configures it. Approval activates
the protocol as the release gate; rejection leaves the thresholds proposed.
