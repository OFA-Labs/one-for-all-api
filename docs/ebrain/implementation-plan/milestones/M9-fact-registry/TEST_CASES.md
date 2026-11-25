# M9 acceptance cases

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
