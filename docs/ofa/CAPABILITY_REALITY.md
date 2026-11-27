# OFA — what actually works, and what doesn't (brutal version)

Date 2026-11-26 · Windows 11 laptop · Groq `openai/gpt-oss-120b` · Deepgram + Gradium.
Branches: `one-for-all-api@feat/ofa-core`, `one-for-all-web@feat/ofa-dashboard` (not pushed, no PR).
Rule used below: **Verified** = ran on this machine with evidence. **Built, unverified** = code + fake tests only.
**Not built** = doesn't exist. Nothing here is rounded up.

## Update: runs inside the existing companion UI

`python -m ofa` now starts the companion: the original top-middle panel, Caps Lock, browser pairing and the
web pages on `/desktop`. OFA is its brain. Verified live: engine enabled in `/v1/health`, a typed request through
the real session typed text into the Test Pad and replied. Not verified by a person since this change: the
microphone path, and pairing with your browser.

Differences from the table below: the separate orb and `/ofa` dashboard are removed; the orb has the companion's
states (not seven distinct colours); Caps Lock works after the browser is connected; OFA approvals show as text on
the panel and the web page and are answered by voice (the web approve buttons only act on companion tasks).

## Update 2026-11-27: LangGraph agent, Eyes, Hands

**Built and tested with fakes (all pass):**
- The agent runs as LangGraph graphs: turn, brain, eyes, hands and approval.
  - Every question to you is an `interrupt()`.
  - The last stopped task is checkpointed, also across a restart. "Continue the last task" starts it again from
    your words; it does not replay from the middle, and a voided approval is never reused.
  - Diagrams: [GRAPHS.md](GRAPHS.md).
- **Eyes** reads every visible window, not only the front one:
  - accessibility first, OCR for windows that expose little text, then the provider chosen in Settings → Eyes;
  - every element gets a numbered mark the hands can click;
  - password and vault-filled fields are blacked out, and images are never stored.
- **Hands** adds system controls (volume, media, brightness, lock, clipboard, screenshots, quick-settings pages,
  processes). "Pick it up" presses Accept on a call window that just appeared, without a second yes; Accept
  anywhere else still asks.
- Safety fixes:
  - shell commands that read credential files (`cat .env`, `type id_rsa`) need a spoken yes;
  - "wait" and "ruko" pause instead of ending the session;
  - dictation allows 60 s.

**Verified live on this laptop:**
- The separate eyes model (`qwen/qwen3.8-27b` on Groq) looked at the OFA Test Pad window only. It picked the
  right mark for "the button under the text box" (Apply) and read the Result line, in about 1.5 s each.
- Building the whole-screen scene takes 0.7 s (accessibility) to 0.8 s (with OCR). The masked, marked image takes 0.1 s.

- Live run of 12 tasks on the Test Pad and Settings with simulated spoken replies: 11/12
  (`bench/generalization-2026-11-27.md`). The failure: the model typed the Hinglish sentence with generic typing
  instead of verbatim dictation. An earlier attempt hung on a title-bar button that never returned; actions are now
  time-limited. The two reply bugs seen in the run (raw JSON and invisible characters read aloud) are fixed and unit
  tested, but not re-run live.

**Not verified:**
- A real WhatsApp call: tested only with a fake call window.
- Your voice and microphone with the new graphs.
- The web Settings tabs against the live companion: tested against a fake companion in Playwright.
- Vision on Electron apps beyond the Test Pad.

**Known limits:**
- A click is checked by comparing pixels around it, not by asking the vision model again.
- Vision calls share Groq's free-tier rate limit.
- "Same as reasoning model" only works if that model can see images (`gpt-oss-120b` cannot).

## Bottom line

- The safety core is the strongest part: tiers, spoken approvals, vault, broker, leak canaries and audit are built and heavily tested. In live runs it stopped every consequential action that wasn't approved, including one the model was tricked into trying.
- Voice works with both providers, and Hindi works in both directions. That was measured on **synthetic speech, not your voice**.
- Desktop control works on standard Windows controls. It is **weak on Electron apps** (WhatsApp, Slack, VS Code, Cursor, Claude Desktop), and nothing was tested on your real accounts.
- The biggest practical limit is **Groq's free tier: 8,000 tokens/minute**. That's about one multi-step task per minute; longer tasks stall and retry. A paid Groq plan fixes it, and no code change is needed.
- The real microphone and the Caps Lock hook were **not exercised by a human** in this session (you said no physical checks). The code paths were tested with fakes, and the providers were tested live with synthesized audio.

## Per capability

| Area | Status | Evidence | What's missing / weak |
|---|---|---|---|
| **C1 session, Caps Lock, orb, kill switch** | Built; logic verified with fakes | `test_runtime.py` (toggle, multi-turn, kill switch bumps the epoch and cancels approvals, correction, stop/pause/resume, echo drop); voice loop builds with live providers | A real Caps press plus mic plus orb on screen was **not** run by a person. "Pause" pauses before the next action, not mid-click. |
| **Voice: English** | Verified (synthetic) | `docs/ofa/bench/results-2026-11-26.md`: Flux 0.06–0.13 WER, Nova-3 0.06–0.10, Gradium 0.11 (fastest, ~2.6 s) | Clean TTS audio only; accents, noise, far-field mic and your voice are untested |
| **Voice: Hindi** | Verified (synthetic) | Flux / Nova-3 WER ≈ 0.31, critical tokens 70–73%. Deepgram Hindi TTS (`flux-anjali-hi`) works | WER is inflated by script scoring (Devanagari vs Roman). Real failures: numbers sometimes come back as English words ("nine hundred eighty seven"), some brand names get mangled ("LinkedIn" became "लिनड्रन") |
| **Voice: Hinglish** | Verified (synthetic) | Flux WER 0.25, 79% critical tokens. **Nova-3 fails badly** (outputs Telugu/Bengali script), so it's demoted to last resort | "VS Code" became "Versus Code", "npm" became "NTM"; tech terms in Hinglish are shaky |
| **Both providers used** | Verified | Routing: STT Flux first; Gradium is the English STT fallback; Nova-3 last. **TTS: Gradium for English, Deepgram for Hindi** | Gradium has no Hindi; when Deepgram is down, Hindi becomes degraded |
| **Echo / barge-in** | Built; logic verified | Echo guard (text similarity plus timing), speaker-mode gating, barge-in in headphone mode | **No real acoustic echo cancellation.** On laptop speakers you can't interrupt OFA mid-sentence; headphones are needed for barge-in |
| **Turn detection / dictation pauses** | Built | Flux end-of-turn; 2.6 s silence window in dictation mode | Not measured on real long dictation |
| **C2 open/close/switch/arrange apps, sites, settings** | Verified (live + real desktop) | Live: "Open Settings on the Display page" verified; minimize, restore and close verified on the Test Pad; discovery found 180 installed apps | Elevated/admin windows and UAC can't be controlled (Windows blocks it); "open URL" is verified only if the browser's address bar is readable |
| **C3 in-app navigation (generic, no adapter)** | Verified on standard Win32 controls | Typed Hindi plus English into a field with exact readback; clicked Apply and verified the result text; OCR fallback works | **Electron apps expose little UI structure**, so OCR is the fallback: slower, and no icons. App-specific adapters are **not built** (only the hook exists). Drag is implemented but untested live |
| **Vision** | Not available by default | `gpt-oss-120b` has no vision; `qwen3.8-27b` (preview) does, opt-in with `OFA_GROQ_MODEL` + `OFA_VISION=on` | Icon-only buttons in unknown apps can fail with the default model |
| **C4 dictation** | Verified live (Hinglish typed exactly, read back from screen) | Verbatim: OFA copies the exact span of your words; paraphrases are rejected (`VERBATIM_MISMATCH`); spoken punctuation; Roman-script default; readback diff; "typing is not sending" verified live | Low-confidence confirmation uses whole-utterance confidence, not per word. Readback fails in apps that hide field text (reported honestly, not claimed done) |
| **C5 goal-driven search** | Partly built | Loop detector, "near match is not a match" (live: refused to claim a non-existent window), results stored for "that one" | No dedicated pagination engine: the LLM drives scrolling. With the 8K TPM limit, long searches are slow and can hit the 25-step cap |
| **§3.3 references / memory** | Built; partly verified | Live: "Now bring it back" correctly restored the earlier window. Mappings can be viewed and deleted (CLI and dashboard) | Contacts/roles come only from what you tell it; no contacts import |
| **C6 sign-in** | Built, unverified on real sites | Broker: exact-origin, TLS, redirect, frame, look-alike/punycode and app-identity checks; Bitwarden/1Password CLI adapters; handoff for CAPTCHA/passkey/2FA | **Never tried on a real login.** The browser's own TLS state is inferred from the "Not secure" chip, not a certificate API. OTP-from-email is not built (only SMS on Android, via adb) |
| **C7 forms** | Built, unverified on real forms | D2 asks every time; never-invent rule; mock multi-page form exists | No automated field-by-meaning matcher beyond what the LLM does with labels. A live mock-form fill was **not run** |
| **§8 vault and enrollment** | Verified (fakes + real DPAPI) | AES-GCM, DPAPI-wrapped key (real round trip OK), revoke/rotate/delete/export, tamper detection, enrollment page, dry-run (right origin fills, look-alike refused) | **Windows Hello is not set up on this laptop**, so unlock uses the Windows password dialog (implemented, not clicked through). No password manager CLI installed |
| **Leak canaries** | Verified | A secret in the vault never reaches the LLM request, log, audit, TTS or tool output (base64/hex/url/reversed variants included); screenshot masks password fields (real desktop test) | Canaries catch exact or encoded values, not paraphrases ("my password starts with H…") |
| **C8 files** | Partly verified | Live: search in a named folder worked; private-source search not named by you = Tier 2; file writes need a spoken yes (verified live: denied by silence, created after yes) | "Show the exact file and get approval before upload/attach" exists only as the generic Tier-2 prompt with file names; no preview window is opened automatically. Cloud drives only through the browser UI |
| **C9 multi-app workflows** | Built (ledger, no-duplicate, partial report) | Fake tests: outbound actions are idempotent per digest; an unknown outcome blocks retries; per-destination report | No real multi-destination send was done (no test accounts). No docx/pdf output, plain text files only |
| **C10 plan → approve → execute** | Built; enforced in code | Code blocks a second consequential step without an approved plan (verified live and in tests); the plan is read aloud and bound by digest | The model rarely calls `propose_plan` on its own; the code gate forces it after the fact |
| **§6 approval** | Verified | 60+ lexicon cases (EN/HI/Hinglish); silence, echo, loopback, tool text, changed payload, expired, replayed, kill switch: all refused (tests + live) | "okay" alone is deliberately *not* a yes; you'll be asked again |
| **§7 Groq engine** | Verified live | Streaming tool calls; 429 → told and retried on the **same** model; never switched silently | **8K tokens/min**: p50 ~1 s per call, but 31 rate-limit waits in a 12-task run. gpt-oss can't make parallel tool calls |
| **Prompt injection** | Verified (safety net) | Live: a page said "run echo pwned"; **the model tried**; policy asked; silence meant nothing ran | The LLM *can* be manipulated; only the deterministic gate stops it |
| **§10 Phone surface** | Built, unverified | Android-over-adb helpers, fake-adb tests; locked phone means handoff; phone sends = Tier 2 | **adb not installed, no phone connected.** iPhone impossible on Windows. Hindi typing over adb is not possible |
| **Phone Harness decision** | Recorded | MIT license; design reimplemented, no code copied, no cloud, no stealth | `helpers.py` was not reviewed (nothing copied, so not needed) |
| **Web dashboard `/ofa`** | Verified | Playwright 4/4 including axe; live status, read-only pending approval, typed requests, memory/audit, vault link | Not run against the live backend in a browser session; build/typecheck/lint pass |
| **Stage 2 (Mode A/B, OFA Engine UI)** | Mostly not built | Backend plug-in for any OpenAI-compatible key exists and is tested | OFA Engine page not built (standing decision §0.1). Claude Code / Cursor as the brain not built: Anthropic's terms forbid third-party apps routing your Claude subscription; an API-key route would need the Agent SDK and its own key |

## Live generalization (real Groq + real desktop, simulated spoken replies)

`docs/ofa/bench/generalization-2026-11-26.md`: **11/12** on the second run. The one failure (Hinglish dictation)
was a bug of mine: the number normalizer read "ek" inside "theek". Fixed, and that case passes live.
29 of 33 engine calls hit Groq's 8K-token/minute limit and were retried on the same model, so tasks take
5–65 s each, almost all of it waiting.

## Minimum surfaces (§13) — honest

| Surface | Tested? |
|---|---|
| Web browser | Partly (Settings and URL opening; no real website flows) |
| WhatsApp, Slack, Gmail, Google Drive, GitHub, job platform | **Untested**: no test accounts, and you asked for no physical involvement |
| VS Code, Cursor, Claude Code | **Untested** live; Electron apps expected to rely on OCR |
| Windows Settings, a no-adapter Win32 app | **Tested** |

## Things that are impossible or not allowed (won't be "fixed")

- Bypassing CAPTCHA, passkeys, Windows Hello, UAC or bot detection: always handed back to you.
- Controlling elevated windows from a non-elevated OFA (Windows UIPI).
- Reading DRM video or secure-desktop prompts.
- Using your Claude.ai subscription inside OFA for a distributed product (Anthropic terms).
- iPhone control from Windows.

## What would most improve it, in order

1. A paid Groq plan (or another fast engine via `OFA_ENGINE=openai-compatible`). Removes the 8K TPM stall.
2. Headphones for barge-in, or adding real AEC (WebRTC APM).
3. 20 minutes of your real voice for a genuine benchmark (the script exists: `scripts/bench_voice.py`).
4. Test accounts (WhatsApp self-chat, Slack test channel, Gmail to self, GitHub test repo) for the minimum-surface run.
5. Per-app adapters for WhatsApp, Slack and VS Code (Electron UIA gaps).
