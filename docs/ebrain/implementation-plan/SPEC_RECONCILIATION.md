# Specification precedence and discrepancies

The owner selected **V3 as the main plan** on 2026-11-24. The handoff remains the research baseline. Actual code determines starting state; V3 determines proposed target behavior; executed evidence determines claims. Existing ADRs remain active until an approved replacement is appended.

`SPEC_DEV_BRAIN_V2.md` contained the complete V3 draft and was byte-identical to the owner’s Downloads `SPEC_DEV_BRAIN_V3.md`. Its contents were preserved under `docs/ebrain/SPEC_DEV_BRAIN_V3.md`. Historical references inside it describe V2 and are not current relative links. No genuine V2 text was reconstructed or invented.

## Milestone crosswalk

| Handoff proposal | V3 implementation destination | Treatment |
| --- | --- | --- |
| Old M7: binding supersedes + fixed-rarity anchor lock | M7 regression fixtures; M9 exact identity; M11 authority/base rules | Do not ship proto_F as the V3 resolver. Binding identity cannot grant permission. Keep near-miss diagnostics and measure both merge and fragmentation. |
| Old M8: batch semantic slot resolver | M9 classifier and identity proposals; M12 advisory maintenance | Approved exact aliases may bind deterministically; model similarity cannot automatically merge existing facts or set current. New model dependencies need D02. |
| Old M9: mode/tier capacity | M8 atomic admission primitive; M14 plan policy and UI | Legacy capacity counts accepted events per user/project; V3 tiers count active canonical facts and separately bound events/bytes/jobs. Never relabel one as the other. |
| Old M10: mode/tier UI | M14, with M13 authenticated clients | Expand to pending, conflict, freshness, completeness, review and intended/observed state; preserve experimental honesty. |
| Old M11: extend frozen catalogue | M7 versioned V3 harness | Preserve harness 1.0.0 byte-for-byte. Add a separate generator/protocol, not an undocumented monkeypatch to frozen scores. |
| Old M12: demonstrate 50k then regenerate facts | M10 retrieval, M12 projections, M13 load, M14 release evidence | V3 requires public+sealed, 100k event and distinct-fact suites and joint answer accuracy. Old .85 target does not satisfy V3 .95. |

## Conflicts to resolve explicitly

| Topic | Existing implementation / handoff | V3 target / planning rule |
| --- | --- | --- |
| M0–M6 status | Source and tests exist; handoff says done, some historical README/log entries still say future | Preserve numbering. Present current observed capabilities and remaining live gaps, not a blanket production-done claim. |
| Lineage | `_assign_chain` can override supersedes with fuzzy match; known path precedes most lineage; multiple targets choose first | Validate one authorized identity, scope, qualifiers and existing base. Conflicting path/lineage or multiple fact targets must reject/review, not choose first. |
| Authority | Legacy T2 allows lower-authority override with explicit supersedes | V3 forbids it without bounded delegation/approved decision. Keep legacy tests; version behavior and approve D03. |
| External data | Legacy external-only chain can be current with untrusted flag | V3 external evidence never establishes current merely by arrival. Evaluate separately from old presence metric. |
| Rollback | `Store.rollback()` physically deletes later rows | V3 append-only compensating event with reviewed target/current base. Never call legacy rollback during migration/recovery. |
| Time | Client integer `ts`, `as_of`, timestamp tie conflict | Server commit cut, valid-time intervals and knowledge cut; concurrency uses observed base, not equal timestamps. |
| Models | No network/model on request paths; embeddings rejected in current ADR | V3 permits approved local query encoders/rerankers and asynchronous filing suggestions; resolver stays model-free. Keep defaults until D02. |
| Budget | Legacy proxy token budgets enforced | Compact mode preserves budget and critical statuses; accuracy-first mode has no token-efficiency target. Report both modes; clipping never hides conflict. |
| Capacity and price | Free soft 800/hard 1000 events, warn; handoff string `PRICE = owner decision` | Preserve legacy defaults. V3 fact-based plan schema has numeric price unset/null; UI may display “Price not set.” No payment or currency invention. |
| 50k evidence | Handoff early sections call it blocked/unmeasured; later sections record extended runs | Raw CSVs show .5006 baseline/.8064 fixed-cap prototype on extended catalogue. Not like-for-like with frozen 1k/10k; auto-cap 50k produced no result. |
| Catalogue arithmetic | Handoff says 2,124 subjects enough for 2,500 chains | 36×59=2,124 per-project candidates; project-qualified identities can yield 4,248 across two projects. Verify actual generator consumption. Do not carry this inconsistent prose into a new capacity proof. |
| Cleanup | Handoff forbids touching offline app/moving FINAL | Owner later explicitly authorized cleanup. Frozen retained files are relocated intact; no product dependency may point at the removed top-level folders. |

V3’s targets (.95 exact/.05 zombie, .98 filing, .99 retrieval, 200 sessions, provisional latency) are **acceptance proposals**, not observed capabilities. Mark an unmet target FAIL/NOT_RUN; obtain an explicit revised ADR before changing it. Choosing this plan does not demonstrate accuracy, approve actual prices, select an external model provider, or authorize destructive production migration.
