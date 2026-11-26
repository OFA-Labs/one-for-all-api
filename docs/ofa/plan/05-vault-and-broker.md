# 05 — Vault, Credential Broker, Egress Guard
**Purpose:** §8 design on Windows · **Depends on:** §8, C6, C7, 04 · **Files likely touched:** `api/ofa/vault/*`, `api/ofa/egress.py`, `api/ofa/ui/vault/*` · **Done when:** M02 (store, broker, canaries) and M08 (enrollment UI, dry-run, PM link) pass rows V1–V12.

## Storage order (§8.3)
1. **Reuse sessions**: browser profile already signed in (paired browse adapter) / app already signed in → no handle needed. Handle kind `session:<service>` records only "use existing session".
2. **Password manager**: adapters `pm_bitwarden.py` (official `bw` CLI, user unlocks with `bw unlock` → session key kept in-memory only) and `pm_1password.py` (official `op` CLI + desktop app unlock). Broker fetches value just-in-time, injects, zeroizes. Browser built-in autofill: trigger by focusing the field and invoking the browser's own autofill UI is NOT reliable → not used for automation; listed as manual handoff.
3. **OFA vault** for D1/D2 profile fields and secrets not in a PM.

## Vault store (`ofa/vault/store.py`)
- SQLite `%LOCALAPPDATA%/OFA/vault/vault.db`. Row: `handle, class, service, label, version, nonce, ciphertext, meta_json, created, last_used, revoked`.
- AES-256-GCM per value; AAD = handle string (prevents swapping rows). Data key (32 B) wrapped by DPAPI (`voice/protected_store.py`, CurrentUser scope).
- **Unlock = OS user presence at session start**: Windows Hello `UserConsentVerifier.RequestVerificationAsync` (winrt); fallback `CredUIPromptForWindowsCredentials` (Windows password). Never by voice. Unlocked key lives in process memory for the session; Caps-off or 30 min idle → wipe.
- Meta (non-secret, LLM-visible): `{class, service, label, allowed_targets[], ops[], tier, created, last_used}`.

## Handle schema
`vault:<D0|D1|D2|D3>/<service>/<label>#<version>` e.g. `vault:D3/github/password#2`, `vault:D1/profile/phone#1`, `pm:bitwarden/<item-id>/password`, `session:gmail`.
`allowed_targets`: exact origins (`https://github.com`) or app identity `{exe_path, publisher (Authenticode subject)}`. No wildcards except explicit `https://*.example.com` set by the user in the UI.

## Broker flow (`ofa/vault/broker.py`) — §8.4
```
fill(handle, field_ref, step) ->
  1 Gate: tier (D2 → Tier 2 ask-each-time; D3 TOTP → Tier 2 per use; login when asked → Tier 1)
  2 identify target: browser → CDP/browse adapter: top-frame URL origin, scheme https, no cert error,
      frame origin of the field == top origin (no cross-origin iframes), not redirected since step observed;
    app → foreground HWND → PID → exe path + Authenticode publisher; UIA element IsPassword/ControlType
  3 compare with allowed_targets (exact string), confusable/punycode check (IDNA decode, skeleton compare)
  4 inject: browser fill via automation set-value on the element; app: UIA ValuePattern.SetValue;
      fallback SendInput typing into the verified focused field. Clipboard never used.
  5 verify: field non-empty (length only) ; zeroize buffer ; canary.register(value)
  -> returns {"ok": bool, "reason": code}   # never the value
```
Refusals (`WRONG_ORIGIN`, `LOOKALIKE`, `REDIRECTED`, `APP_MISMATCH`, `REVOKED`, `LOCKED`) are spoken to the user.

## Egress guard + leak canaries (`ofa/egress.py`)
- Single chokepoint: Groq HTTP client, logging `Handler`, transcript writer, audit writer, screenshot uploader, TTS text input. Code review rule + test (`test_no_bypass.py`) greps that no other module imports `httpx` for engine hosts or opens log files directly.
- Fingerprints held in memory for each released or loaded secret value: raw, lowercase, base64, url-encoded, hex, and with whitespace stripped; Aho-Corasick or set-of-substrings scan (values ≥ 6 chars; shorter D3 values are padded-matched on exact field).
- Hit → block the send, raise `LeakBlocked`, speak "I blocked a message that contained a secret", audit (handle id only).
- Synthetic canaries: at test and at every session start the broker loads 2 random canary secrets (`ofa-canary-<random>`) into the vault; any appearance outbound = test failure / runtime alarm.

## Screenshot redaction (§8.4)
Before any screenshot leaves the process: black boxes over UIA `IsPassword` elements, browser `input[type=password]`, any field the broker filled this session, and user-flagged regions. Vision upload default OFF (06: default model has no vision). OCR runs locally (Windows OCR).

## D1 release to engine
Default: labels only. A task needing D1 text to compose (e.g. cover letter with city) → orchestrator requests `release(fields)`; Tier 1 if user asked for that composition, logged; user setting `never_send_D1_to_cloud=true` blocks it → OFA says it can fill but not compose with those fields.

## Enrollment (`ofa/ui/vault/`, loopback page, §8.5) — M08
- Served at `http://127.0.0.1:8767/vault#token=<per-process random>`; opened by `python -m ofa vault`. Values posted UI → broker only; request bodies never logged.
- Wizard: (1) link PM (detect `bw`/`op`, test unlock), (2) mark reusable signed-in sessions, (3) profile in groups D0 / D1 / D2 with per-class prefs, (4) optional secrets for services not in a PM. Plaintext import: not offered; CSV import shows a warning and requires a checkbox.
- Manage: list handles (meta only), rotate (new version), revoke, export (encrypted JSON, needs Hello), delete.
- **Dry-run fill**: local mock form `http://127.0.0.1:8767/mock/login` + `/mock/form` (multi-page, conditional field) to show fill working; plus a look-alike mock origin `http://localhost:8767` that must be refused.

## Tests (ids used in 08)
V1 canary never in Groq payload · V2 never in logs/transcripts/audit · V3 encoded variants blocked · V4 screenshot masks password field · V5 wrong origin refused · V6 punycode look-alike refused · V7 TTS input with secret blocked · V8 revoke → fill fails · V9 tamper ciphertext/AAD → decrypt fails · V10 locked vault → `LOCKED` · V11 enrollment request bodies absent from logs · V12 dry-run mock fill succeeds.
