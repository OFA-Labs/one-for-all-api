# 03 — Voice
**Purpose:** provider facts, routing, benchmark, Hindi/Hinglish, echo · **Depends on:** §4, C1, C4 · **Files likely touched:** `api/voice/{deepgram,gradium,failover,audio,session}.py`, `api/ofa/voice_router.py`, `api/ofa/text/{hi_numbers,translit}.py` · **Done when:** M04 benchmark committed and router uses its results.

## Verified facts (fetched 2026-11-26)
| Fact | Source |
|---|---|
| Deepgram Flux STT: `flux-general-en`, `flux-general-multi` on `/v2/listen`; multi languages en, es, fr, de, **hi**, ru, pt, ja, it, nl | developers.deepgram.com/docs/models-languages-overview ; /docs/flux/language-prompting |
| Nova-3 `language=multi` (55 langs per guide), overview lists Hindi | /docs/multilingual-code-switching ; overview |
| Deepgram TTS page lists Aura-1/Aura-2 only; languages en, es, de, fr, nl, it, ja; **no Hindi voice found**; "Flux TTS" not found | /docs/tts-models |
| Deepgram Voice Agent API; Hindi `numerals`: not found in pages read | — (re-check M04) |
| Gradium STT ws `wss://api.gradium.ai/api/speech/asr`, `json_config.language="any"`; semantic VAD steps every 80 ms with `inactivity_prob` at 0.5/1/2/3 s; `send_flush()` | docs.gradium.ai/guides/speech-to-text.md |
| Gradium TTS ws `/api/speech/tts` + REST, 48 kHz PCM; voice cloning, voice design, localization; "five languages"; **Hindi not found** | docs.gradium.ai/guides/text-to-speech.md ; /voices/overview.md |
| Existing code: Deepgram STT = nova-3 multi `/v1/listen`; TTS `/v2/speak` with `voice_for(language)` | api/voice/deepgram.py:29-88 |

**Conflict:** §4.1 and `docs/voice/README.md` say Deepgram TTS speaks Hindi; today's docs page did not show it. M04 step 1 = one live `/v2/speak` Hindi call. If it fails → Hindi replies use **degraded mode**: speak Roman Hinglish with an English voice and announce it once per session (§4.2 "announce degraded").

## Provider interface (keep `voice/contracts.py`, extend)
```python
class SttProvider(Protocol):
    name: str; languages: set[str]; turn_detection: Literal["none","vad","semantic","flux"]
    def stream(self, frames, *, language: str, mode: Literal["command","dictation"]) -> AsyncIterator[Transcript]
class TtsProvider(Protocol):
    name: str; languages: set[str]
    def stream(self, text: str, language: str) -> AsyncIterator[Audio]
# Transcript gains: words[(text, conf, start, end)], is_final, end_of_turn, language_detected, script
```

## Routing (initial; M04 benchmark may change it, recorded in PLAN-DELTAS)
| Capability | en | hi / Hinglish | Fallback |
|---|---|---|---|
| STT command mode | Flux multi vs Gradium (benchmark picks) | Deepgram Flux multi vs Nova-3 multi (benchmark picks) | en: other provider; hi: other Deepgram model, else degraded notice |
| STT dictation mode | provider with best long-pause handling (Gradium semantic VAD candidate) | Deepgram + OFA pause policy | same |
| Turn detection | Flux end-of-turn / Gradium inactivity_prob ≥ 0.9 @2 s | Flux end-of-turn | local VAD + 1.2 s silence (command), 3.0 s (dictation) |
| TTS | Gradium vs Deepgram Aura-2 (benchmark picks) | Deepgram if Hindi works, else degraded | other provider for en only |
**Both used:** Deepgram is mandatory for Hindi; Gradium owns at least one English role (TTS or STT or dictation turn detection) per benchmark; if Gradium wins nothing, it stays as the English fallback and the report says so honestly.
No silent provider switch for *reasoning*; voice fallback is allowed but is announced once ("switching voice provider") and logged.

## Hindi / Hinglish text handling (`api/ofa/text/`)
- `hi_numbers.py`: parse Hindi number words in Devanagari and Roman (ek…sau, hazaar, lakh, crore, dedh, dhai, saadhe, paune, sava), dates ("parson", "kal", month names), times ("saadhe paanch baje", "shaam ke 7"). Pure function, 60-case table test.
- `translit.py`: detect script per token; Devanagari→Roman Hinglish (default; user pref `script=roman|devanagari|as_spoken`). Rule: only script changes, never word choice; round-trip test asserts token count + order unchanged.
- Code-switch: never translate; `language` tag only drives TTS voice.

## Echo, barge-in, noise
- OFA-media guard (§4.2, §6): (a) capture gated while TTS plays in speaker mode (existing); (b) every final transcript compared with the last 30 s of OFA TTS text (`rapidfuzz.partial_ratio ≥ 80` → drop); (c) transcripts beginning < 400 ms after TTS end are discarded for approvals; (d) headphone mode enables barge-in: user speech energy + STT partial during TTS → stop TTS within 200 ms.
- AEC: evaluate WASAPI communications-mode capture (Windows built-in AEC/NS) in M01; if unavailable, keep gating and report "no full AEC" (current honest status in README).
- Approvals additionally require (04): approval window open, mic source = default capture device, not loopback.

## Benchmark (M04; small and fixed, §4.2)
| Set | Count | Content |
|---|---|---|
| EN | 20 | names, numbers, negations ("don't send"), tech terms (repo, PR, npm) |
| HI | 20 | Devanagari-native commands, Hindi numbers/dates/times |
| Hinglish | 20 | mixed commands + dictation with pauses |
- Recorded by the user with consent via `scripts/bench_record.py`; audio in `_local/bench/audio/` (never Git); references in `docs/ofa/bench/refs.yaml` (text only).
- Metrics: WER, critical-token accuracy (names/numbers/negations), end-of-turn false cut rate, latency p50, TTS MOS-lite (user rates 1–5 on 5 samples each), cost/min. Results → `docs/ofa/bench/results-<date>.md`; rerun only if providers change.
