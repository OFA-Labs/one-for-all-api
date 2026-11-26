# 04 — Approval Engine, Threat Model, Audit
**Purpose:** deterministic enforcement of §6 and §8.7 · **Depends on:** §6, §8, 02 · **Files likely touched:** `api/ofa/policy/*`, `api/ofa_execution/policy.py`, `api/ofa/audit.py` · **Done when:** M02 approval test suite (08 rows A1–A14) passes.

## Principles
1. The approval engine lives below the engine, voice provider and harness. It reads only: the step object, the approval store, the session epoch, the speech listener. Nothing the LLM writes can create an approval.
2. The engine may **raise** a tier, never lower it. Unknown verb/effect → Tier 2.
3. Spoken text for approval is rendered by a **deterministic template from the exact step fields**, so the user approves what will run.

## Tier classifier (`ofa/policy/tiers.py`)
| Input | Rule |
|---|---|
| Verb in {navigate, scroll, read, screen, find, public search, draft-unsent} | Tier 0 |
| Verb in {open named item, sign-in when asked, fill non-sensitive field when asked} **and** `authorized_by_turn` names the target in the user's own transcript this epoch | Tier 1; else Tier 2 |
| Verb in §6 Tier-2 list, or any `fill` of D2/D3 handle, any TOTP release | Tier 2 |
| `click`/`key` where the element label/role or context matches the effect lexicon (send, post, submit, pay, buy, book, delete, share, merge, publish, apply, bhejo, bhej do, भेजें, भुगतान, हटाएं …) or Enter in a compose/message/command field | Tier 2 (§6 "any Tier 2 effect") |
| Shell/terminal command | Tier 2 unless matches read-only allowlist (`ls`, `git status`, `git diff`, `cat` within allowed roots) |
| Private-source search not opened by the user | Tier 2 |

## Approval request (`ofa/policy/approval.py`)
```python
@dataclass(frozen=True)
class ApprovalRequest:
    id: str; epoch: int; step_id: str; action: str
    digest: str        # sha256(canonical_json(action, payload_sha, destinations[], account, file_sha256s[]))
    spoken: str        # template output; full text if payload ≤ 280 chars, else summary + on-screen exact item
    created: float; expires: float    # ttl 45 s
class ApprovalState(Enum): PENDING, GRANTED, DENIED, EXPIRED, INVALIDATED, CONSUMED
```
Flow: `Gate.check` → Tier 2 → `approval.ask(step)` → orb=`awaiting_approval` → TTS(spoken) → listen window opens 400 ms after TTS end, closes after 8 s → `lexicon.classify(final_transcript)`:
- `YES` → GRANTED → `Gate.sign()` one-use token bound to `(task, step digest, observation hash, epoch)` (existing mechanism).
- `NO` → DENIED, tell engine "user declined" (data).
- `UNCLEAR`/`MODIFY` ("yes but…", "haan lekin…") → no approval; transcript forwarded to engine as a revision request → new step → new request.
- Silence → re-ask once ("Should I go ahead? Please say yes or no."), then EXPIRED + report.
At consume time: recompute digest from the step about to execute; mismatch, expired, epoch change, or token reuse → refuse + audit.
Multi-destination: one request may list N destinations only if `spoken` names all N; digest includes all; any change → new request.

## Yes/No lexicon (`ofa/policy/lexicon.py`; whole-utterance match after normalization + translit to Roman)
| Class | Patterns (extendable in config, never by the LLM) |
|---|---|
| YES | yes, yeah, yep, yes please, sure, go ahead, do it, send it, confirm, confirmed, "ok go ahead"; haan, haan ji, ji haan, haanji, bilkul, theek hai, kar do, bhej do, haan bhejo, haan karo, chalo karo; हाँ, हां, जी हाँ, बिल्कुल, ठीक है, कर दो, भेज दो |
| NO (wins if any token present) | no, nope, don't, do not, stop, cancel, wait, hold on; nahi, nahin, mat, ruko, rehne do; नहीं, मत, रुको, रहने दो |
| UNCLEAR | everything else, incl. bare "ok/okay/hmm", questions, conditionals ("if", "agar"), "but/lekin/par" |
Additional gates for YES: speaker-check passes (03 echo guard), STT confidence ≥ 0.80 on the yes tokens, source = mic.

## Threat model (§8.7 scope)
| Threat | In scope | Control | Test |
|---|---|---|---|
| Prompt injection in page/message/doc/PR/tool/harness output | yes | `untrusted` wrapping; tier classifier ignores content; approvals only from listener | A8, A9 |
| Look-alike / phishing domain, redirect | yes | broker exact-origin + TLS check, punycode/confusable check (05) | V5, V6 |
| LLM exfiltration of secrets | yes | handles only; egress guard canaries | V1–V3 |
| Log/transcript/audit leakage | yes | all writers go through `egress.guard` | V2 |
| Screenshot leakage to cloud | yes | redaction before egress; vision off by default | V4 |
| Voice leakage (speaking secrets) | yes | TTS path through egress guard; D2/D3 never in spoken templates | V7 |
| Replayed / echoed approval (OFA's own TTS, media playing "yes") | yes | echo guard, window timing, single-use digest token, epoch | A5–A7 |
| Malware already running as the user | **out of scope** (stated) | — | — |
| Other local users / network | yes | loopback bind, per-process auth token, per-user data dir (`%LOCALAPPDATA%`) | Q1 |

## Audit log (`ofa/audit.py`)
- Append-only JSONL `%LOCALAPPDATA%/OFA/audit/<YYYY-MM>.jsonl`; each line `{ts, epoch, task, step, tier, kind, digest, handle_ids[], result, prev_sha}` (hash chain).
- Never values, transcripts of D1–D3, or tokens. Passes through `egress.guard` like everything else.
- CLI: `python -m ofa audit show --last 20`, `python -m ofa audit purge --before <date>` (purge itself audited).

## Kill switch
Caps press during active session → epoch++ → all PENDING → INVALIDATED, executor drains queue without running, hands `stop()`, TTS stops, orb=idle. Test A10.
