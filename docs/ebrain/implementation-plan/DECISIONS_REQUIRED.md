# Decisions and activation gates

Plan/cleanup scope is authorized. Actual company rollout, model/architecture ADR changes, prices, retention and migration policy remain proposals. Prepare concrete code/ADR/test previews before requesting a gated activation. Continue independent deterministic work while waiting; do not stop the whole project for an unset price.

| ID | Reviewable decision | Recommended proposed default | Needed by | Status |
| --- | --- | --- | --- | --- |
| D01 | Adopt Postgres V3 transaction boundary, schema-3 negotiation and single-writer migration | Separate V3 implementation; legacy stays usable; isolated Postgres for development | M8 activation | PROPOSED |
| D02 | Replace ADR-2/no-model and embeddings rejection for explicitly scoped local accelerators | Async filing suggestions only; approved local query encoder/reranker; model-free resolver; no external fallback | M9 model activation / M10 vector | PROPOSED |
| D03 | Authority, delegation, direct/source assertion and conflict rules, including legacy T2/T3 change | Domain-scoped server grants; lineage is never permission; intended/observed distinct | M8 contracts; M11 semantic activation | PROPOSED |
| D04 | Source contracts, required qualifiers, freshness and pilot domains | Start with explicit engineering repo/project; unknown stays pending; sanitized reviewed evidence | M9 filing | PROPOSED |
| D05 | Retention/erasure/residency, audit minimization, independently recoverable suppression | No raw permanent transcripts; restricted synthetic tests until policy approved | M8 schema design; M13 real pilot | PROPOSED |
| D06 | Distinct-fact tier ladder + separate event/byte/job/rate/emergency budgets | Preserve legacy free warn; V3 plans separately count facts and accepted history | M14 plan activation | PROPOSED |
| D07 | Model artifacts, hardware, runtime/checksums, calibration and permitted egress | Measure local candidates; pin exact validated manifest; egress disabled | M9/M10 model experiments | UNSELECTED |
| D08 | Scope ownership, two-person high-risk review, staffing, SLA and single-user exception | No company self-approval; blocked high-risk action if no eligible reviewer | M11/M13 workflows | PROPOSED |
| D09 | SLO/evaluation protocol and independent sealed evaluator | Retain V3 targets; record hardware and every failed seed/stratum | M7 protocol; M13 release proof | PROPOSED |
| D10 | SSO/OIDC provider, SCIM and agent/session credential delivery | Explicit issuer/audience+membership; no NEXT_PUBLIC static bearer in company builds | M13 identity integration | UNSELECTED |
| D11 | Migration maintenance window, cutover authority, reverse-event support | Rehearsed freeze+final delta; one writer; forward repair if reverse mapping unproven | M14 real migration | PROPOSED |
| D12 | Prices/commercial integration | Numeric price null/unset; display undecided; checkout out of scope | Optional paid commercial launch | UNSET; does not block technical tiers |

For each approved decision append a new ADR to `docs/ebrain/DECISIONS_LOG.md` with owner evidence, date, old/new rule, alternatives, affected schemas/config/manifests, test evidence, activation/rollback and historical compatibility. Keep `tools/ebrain/legacy/FINAL/11-decisions.md` frozen; link its superseding ADR externally. Do not edit the reference spec to make the old benchmark appear to have used new rules.

The main-plan selection does not by itself approve an external model call, actual data migration, a legal retention policy or payment configuration. A coding agent may implement reviewed designs behind disabled flags and test synthetic isolated environments; the relevant activation must wait for its concrete approval when required. Approval is recorded once and reused; it is not requested at every checkpoint.
