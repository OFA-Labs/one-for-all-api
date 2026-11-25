# E-Brain V3 — Individual Developer Edition scope addendum

Owner directive dated 2026-11-25. This addendum supersedes enterprise-scale
requirements **only where they conflict** with a single-developer release. It
does not waive integrity, authority, evidence, erasure or accuracy gates.
Existing M7-M14 code, tests and evidence are retained; nothing is restarted.

## In scope

One real human owner, multiple AI agents/tools (OpenCode, Claude Code, Codex,
MCP agents, OFA web dashboard, voice client), multiple repositories and
sessions. Persistent shared memory with authoritative current-vs-historical
resolution, evidence-backed answers, compact budgets, self-healing maintenance,
Schema 3 clients with safe Schema 1 compatibility, local PostgreSQL/pgvector,
focused synthetic + pilot evaluation, local encrypted backup/restore drill.

## OUT_OF_SCOPE_CURRENT_RELEASE (retain code behind disabled flags)

| Requirement | Classification | Reason |
| --- | --- | --- |
| 100-200 concurrent developers / multi-user production | OUT_OF_SCOPE_CURRENT_RELEASE | Product scope reduced to one owner |
| Enterprise load matrix / 200-session saturation / endurance | OUT_OF_SCOPE_CURRENT_RELEASE | Replaced by 1/3/5 same-owner agent sessions |
| Organization onboarding / tenant administration / org role UI | OUT_OF_SCOPE_CURRENT_RELEASE | No organization in current release |
| SCIM provisioning / live OIDC/Google OAuth / Entra ID | OUT_OF_SCOPE_CURRENT_RELEASE | Deferred (D10); seams retained, disabled |
| Multi-person approval + mandatory backup steward | OUT_OF_SCOPE_CURRENT_RELEASE | Single-user exception; high-risk real operations still blocked |
| Subscription tiers, pricing, billing, paywalls | OUT_OF_SCOPE_CURRENT_RELEASE | Price NULL; no commercial integration |
| Enterprise SLAs, availability targets | OUT_OF_SCOPE_CURRENT_RELEASE | No production service |
| Production cutover, deployment, production DR certification | OUT_OF_SCOPE_CURRENT_RELEASE | Explicitly not authorized |
| Paid/hosted/external inference | OUT_OF_SCOPE_CURRENT_RELEASE | Local offline candidates only |

Removed items are **NOT RUN / OUT_OF_SCOPE_CURRENT_RELEASE**, never PASS.
Checkpoint IDs for these items keep their original numbering for traceability.

## Still mandatory for this release

Deterministic authority (no agent self-escalation, no ambiguous merges), atomic
admission/idempotency, RLS and scoped grants, append-only evidence, suppressions,
all 30 C/H/M findings that are not explicitly scoped out, joint exact quality
targets on the focused suite, zero leakage and zero lost acknowledged writes,
and real cross-session memory persistence.

## Individual benchmark profile

1k / 10k memories (50k only if timebox permits); 1, 3 and 5 concurrent agent
sessions from the same owner; 80% reads / 20% writes; semantic, exact-identifier
and repo-specific queries; revisions/conflicts; background consolidation;
restart persistence. Targets remain >=.95 joint exact, >=.99 authorized recall,
>=.98 filing, zero leaks, zero lost writes, and provisional p95 <200 ms
retrieval+resolver excluding synthesis.
