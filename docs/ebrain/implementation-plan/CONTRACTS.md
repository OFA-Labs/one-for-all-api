# Versioned contract to implement

Freeze executable JSON Schema/OpenAPI plus fixtures in M7; the following is the intended contract. Existing `ebrain/models.py` and web `contracts.ts` are schema-1 contracts and remain covered. New routes stay under `/v1/ebrain` with explicit schema negotiation, e.g. `X-EBrain-Schema: 3`; finalize the wire mechanism in D01 and never infer V3 from an unknown field.

## Domain and invariant fields

- Canonical key: organization + scope + resource namespace/stable ID + predicate + claim kind + normalized required qualifiers. Fact ID is opaque/stable, never a text cluster ID or mutable path.
- Claim: sanitized source snapshot/span, typed normalized value, source contract, admitted principal/grant/policy, valid interval, base/observed cut and immutable code. A source proves an assertion was made, not truth.
- Snapshot: `org_id`, `knowledge_seq`, `valid_at`, `identity_generation`, `policy_version`, `auth_epoch`, compatible retrieval/model generations. Recorded time is server assigned; valid intervals are half-open UTC intervals. Unknown legacy time is explicit.
- Receipt: op ID, committed sequence, `applied|accepted_pending|accepted_noncurrent|conflict|rejected`, processing URL, request digest and idempotent replay marker. Distinguish transition application from search projection lag.
- Answer: `answer_status=complete|partial|ambiguous|pending|not_found|unavailable`; per-fact `state=absent|current|conflict|withdrawn|pending_verification|unknown`; separate claim annotations, freshness/confidence, current typed value or null, approved sources, snapshot, degradation and receipt.
- Exactly one scalar current value, complete resolved set only for supported multi-valued predicates. Initially reject unsupported multi-valued writes explicitly rather than flattening them. A conflict/pending/withdrawn fact has no scalar current. Recommendations, derived and external evidence cannot establish current.

## API surfaces and compatibility

| Surface | V3 behavior / migration obligation |
| --- | --- |
| Write | Server identity; explicit authorized scope, typed assertion or safe text, idempotency key, source, valid interval, expected head/observed sequence. 201 new durable applied/noncurrent/conflict; 202 pending; 200 authorized replay. Legacy 200 accepted=false behavior stays in schema 1 only. |
| Operation status | Authorized viewers only; current processing and reason; no raw hidden payload/existence leak. |
| Query | Structured selector or text/facets, time mode, min_seq, response mode, history and budget. No hidden write or scope expansion. Exact result resolves at authoritative cut even with index lag. |
| Cards/history/decisions | Scoped signed cursor, pinned snapshot, current grants rechecked each page. Cards are derived read views; clients cannot overwrite them. Qualified paths/codes may return historical and current separately. |
| Proposals/review | Immutable revision/digest, evidence/targets/preconditions, expiry, reviewer authority and separation of duties. Approval and authoritative action atomic; stale review -> 409. |
| Receipts/ack | Generated/sent separate from authenticated client ack and client-reported use. Missing = unknown. Feedback never updates current. |
| Rollback | Scoped reviewed compensating decision, new event/code, current base and reason; never delete accepted history. Physical recovery separate. |
| Maintain | Authorized dry-run/idempotent job request, scoped job type; cannot approve identity/decision changes. Legacy agent maintenance access must not bypass V3 admin grant. |
| Limits | Authorized scope only; plan revision/mode/tier, active fact count/capacity/reservations, separate event/byte/job/rate budgets and evidence status. Price unset until supplied. Legacy event count remains separately named. |
| Me/erasure | Authenticated governed request with scope/status; shared engineering decisions not silently erased by a contributor’s account deletion. Payload suppression/erasure controlled separately. |
| MCP | Read/query/evidence/propose/write tools delegate to same services and grants. No SQL, shell, unrestricted files or arbitrary URL fetch; receiving data never authorizes action. |

Errors: 400 malformed, 401 unauthenticated, 403 when existence is safe or indistinguishable 404 otherwise, 409 reused idempotency key with different digest/stale base/review, 413 size, 422 semantics, 429 quota/rate, 503 unavailable. Body `{code,message,request_id,retryable}`; only authorized detail, Retry-After where relevant. After a timeout with uncertain commit, retry same idempotency key/read receipt; never generate a new write blindly.

## Client handling

The CLI, voice pack, web and MCP must negotiate schema and preserve conflict/pending/partial. A legacy client unable to represent unsafe state gets explicit incompatibility or an empty labelled unavailable pack, never a flattened old “current.” Unconfigured pack remains nonblocking. Web server holds secrets and issues scoped sessions; ordinary UI role/localStorage is not authorization. Scope flows through every method, including heal/pair replacements and pagination.

Compact budget clipping reserves room for scope, state, conflicts, pending and critical evidence before optional prose/history; mark omitted facets/incomplete. Accuracy-first returns the declared full structured answer. Scoring checks actual delivered content and internal authoritative state separately.
