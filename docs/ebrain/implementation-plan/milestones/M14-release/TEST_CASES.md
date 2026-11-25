# M14 acceptance cases

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
