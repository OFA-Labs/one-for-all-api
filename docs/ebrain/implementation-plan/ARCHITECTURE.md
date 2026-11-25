# Target architecture and code ownership

This is a proposed implementation layout, not a claim these modules exist. Keep the legacy service intact during construction. Add V3 behind an explicit disabled-by-default schema/backend configuration until compatibility and migration gates pass. One writer is authoritative at any point.

## Boundaries

1. **Authentication/admission** derives principal, grants, scope, predicate authority and source contract; bounds and sanitizes payloads before persistence/logging/model input.
2. **Authoritative ledger** atomically commits normalized evidence, claim/identity/decision/control events, monotonic organization commit cut, idempotency receipt, usage reservation, pending-impact fence and outbox job. Acknowledged means committed, not merely queued.
3. **Fact registry and identity ledger** provide stable typed fact identity independent of search and cards. Source snapshots are immutable sanitized revisions with verifiable spans. Unknown required qualifiers stay unknown.
4. **Pure resolver** uses approved identity, claims, policy/source status, grants-at-admission, valid time and knowledge sequence. No similarity/model/card score or client usage decides current. Current authorization is separately enforced at reads.
5. **Projections/search** are disposable versioned accelerators. Workers are at-least-once, jobs idempotent, watermarks contiguous. Query supplements index lag using authoritative exact/delta data, then resolves at one snapshot. Pending eligible impacts suppress stale current.
6. **Answer/clients** expose fact state, answer completeness, freshness, confidence, sources, receipts and degradation separately. Optional prose/voice compaction cannot upgrade authority or hide uncertainty.

## Proposed backend paths

| Path within API | Ownership and permitted dependencies |
| --- | --- |
| `ebrain/v3/contracts.py`, `errors.py`, `config.py` | Strict versioned schemas, reason codes, immutable policy/semantic config. No side effects at import. |
| `ebrain/v3/auth/` | Principal, grant, delegation and OIDC/session validation; current auth epoch. No authority from request text. |
| `ebrain/v3/db/`, `migrations/ebrain_v3/` | Postgres adapter, transaction-local context, runtime role/RLS, ordered commit and SQL migrations. Pin chosen driver/migration tool after checking current official docs; preserve existing pins. |
| `ebrain/v3/ingest/`, `sources/` | Pre-persistence gate, typed parsing, source snapshots/spans/checkpoints, idempotent admission. |
| `ebrain/v3/identity/` | Canonical keys, registry constraints, identity event replay, approved aliases, correction/merge/split manifests. |
| `ebrain/v3/resolver/` | Deterministic eligibility, interval/base/conflict/lifecycle reducer. No DB/model import in pure reducer; storage loads validated inputs. |
| `ebrain/v3/workers/`, `projections/` | Transactional outbox, leases, retry/dead letter, cards, rebuild/diff and generation activation. |
| `ebrain/v3/retrieval/`, `models/` | Scoped exact/FTS/vector/graph candidates, protected union, calibrated rerank/widening, model manifests. Never mutate identity/current. |
| `ebrain/v3/review/`, `receipts/`, `quotas/`, `lifecycle/` | Immutable proposal/vote workflow, authenticated transport feedback, reservations/settlement, erasure/suppression/recovery. |
| `ebrain/v3/api.py`, `compat.py`, `mcp.py` | Thin shared service calls; schema negotiation, legacy compatibility, authorized tools. No duplicate authority implementation. |
| `tests/v3/`, `tests/v3/integration/`, `tests/v3/security/` | Pure/property tests, real Postgres, restricted roles, adversarial and recovery checks. |
| `tools/ebrain/v3-eval/`, `tools/ebrain/operations/` | Separate test oracle, versioned datasets/results, migration/load/restore tools and manifests. Not imported by product runtime. |

The layout may be simplified when a module has one responsibility; do not create empty frameworks. Preserve the module boundaries and test contracts. Use real isolated Postgres from the first team foundation; SQLite remains the labelled legacy/local adapter. This plan does not select a production cloud, SSO provider, local model, GPU, embeddings dimensions or database extension version without measurements.

## Query integration sequence

Authenticate/authorize query scope -> begin repeatable snapshot and choose committed cut -> interpret qualified selectors/facets -> union authorized exact/FTS/vector/graph and unindexed delta candidates -> preserve protected matches -> verify source/identity/qualifiers -> replay using one policy/identity/time cut -> apply pending fences/freshness -> widen or declare partial/ambiguous -> budget-safe assembly -> final current authorization epoch check -> scoped receipt and delivery. Changed auth epoch requires retry/fail-closed. Current authorization must apply even to old history.

## Early dependency interfaces

M8 defines `Snapshot`, `AdmissionReceipt`, `AuthorizedContext`, `PendingImpact`, an input loader and pure resolver protocol; a deterministic minimal exact fixture reducer supports consistency tests. M9 binds claims and emits identity events without requiring semantic retrieval. M10 returns candidate sets + provenance/watermarks; it does not implement T1–T7 itself. M11 supplies the full independently tested reducer and approvals, completing M10 integration. M12 materializes that same authoritative state, while an independent test interpreter detects shared implementation errors. M13 exercises every layer through real client and restricted runtime roles; M14 cuts over only after these gates.

## Flags and rollback

New V3 shared/mutating paths default disabled. Hard authorization, secret gate, evidence eligibility, current cardinality, approval and audit are not togglable away. Separate operational knobs from semantic versions. Disabling a model falls back to exact/pending and explicit degraded retrieval, not another unapproved provider. Reverting a model/projection pointer is safe only when compatible with the current ledger/auth/suppression cut; reverting production database state is not an ordinary feature rollback.
