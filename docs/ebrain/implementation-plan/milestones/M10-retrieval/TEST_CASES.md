# M10 acceptance cases

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
