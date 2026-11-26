"""Small fixed voice benchmark (§4.2, plan 03). Synthesizes the reference set with provider TTS (cached),
then runs every STT candidate and writes docs/bench/results-<date>.md. Live calls count against live_budget.

    .venv-ofa/Scripts/python.exe scripts/bench_voice.py
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import time
import wave
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ofa import live_budget  # noqa: E402
from ofa.config import secret  # noqa: E402
from ofa.speech.flux import FluxStt  # noqa: E402
from ofa.text.translit import to_roman  # noqa: E402
from voice.config import Settings  # noqa: E402
from voice.deepgram import DeepgramStt, DeepgramTts  # noqa: E402
from voice.gradium import GradiumStt, GradiumTts  # noqa: E402

WS = ROOT.parent
REFS = WS / "docs/bench/refs.yaml"
AUDIO = WS / "_local/bench/audio"
CACHE = WS / "_local/bench/cache.json"


def norm(s: str) -> str:
    s = to_roman(s).lower().replace("’", "'")
    s = re.sub(r"[^\w\s':.,]", " ", s)
    s = re.sub(r"(?<!\d)[.,](?!\d)", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref).split(), norm(hyp).split()
    d = [[i + j if i * j == 0 else 0 for j in range(len(h) + 1)] for i in range(len(r) + 1)]
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    return d[len(r)][len(h)] / max(1, len(r))


def crit_ok(crit: list[list[str]], hyp: str) -> tuple[int, int]:
    h = " " + norm(hyp) + " "
    good = sum(any(f" {norm(str(alt))}" in h or norm(str(alt)) in h for alt in group) for group in crit)
    return good, len(crit)


async def frames(pcm: bytes):
    for i in range(0, len(pcm), 9600):
        yield pcm[i:i + 9600]
        await asyncio.sleep(0.01)


async def synth(provider, text, lang) -> bytes:
    pcm = b""
    async for a in provider.stream(text, lang):
        pcm += a.pcm
    return pcm


async def transcribe(provider, pcm) -> tuple[str, float]:
    start, final = time.monotonic(), ""
    async for t in provider.stream(frames(pcm)):
        if t.final:
            final = t.text
    return final, time.monotonic() - start


def save_wav(path: Path, pcm: bytes, rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1), w.setsampwidth(2), w.setframerate(rate), w.writeframes(pcm)


def load_wav(path: Path) -> bytes:
    with wave.open(str(path)) as w:
        return w.readframes(w.getnframes())


async def main() -> None:
    dg = secret("DEEPGRAM_API_KEY").get_secret_value()
    gr = secret("GRADIUM_API_KEY").get_secret_value()
    s = Settings(mode="live", deepgram_key=dg, gradium_key=gr)
    refs = yaml.safe_load(REFS.read_text(encoding="utf-8"))
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    voices = {"en": [("dg", DeepgramTts(s), "en"), ("gr", GradiumTts(s), "en")],
              "hi": [("dg", DeepgramTts(s), "hi")], "hinglish": [("dg", DeepgramTts(s), "hi")]}
    stts = {"flux-multi": lambda: FluxStt(dg), "nova3-multi": lambda: DeepgramStt(s), "gradium": lambda: GradiumStt(s)}
    rows = []
    for lang, items in refs.items():
        for item in items:
            for vname, tts, vlang in voices[lang]:
                wav = AUDIO / f"{item['id']}-{vname}.wav"
                if not wav.exists():
                    live_budget.spend("gradium" if vname == "gr" else "deepgram")
                    save_wav(wav, await synth(tts, item["text"], vlang))
                pcm = load_wav(wav)
                for sname, make in stts.items():
                    if sname == "gradium" and lang == "hi":
                        continue          # Gradium does not list Hindi; measured for EN and Hinglish only
                    key = f"{item['id']}|{vname}|{sname}"
                    if key not in cache:
                        live_budget.spend("gradium" if sname == "gradium" else "deepgram")
                        try:
                            hyp, secs = await asyncio.wait_for(transcribe(make(), pcm), 30)
                        except Exception as exc:
                            hyp, secs = f"<error {type(exc).__name__}>", 0.0
                        cache[key] = {"hyp": hyp, "secs": round(secs, 2)}
                        CACHE.parent.mkdir(parents=True, exist_ok=True)
                        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
                    hyp, secs = cache[key]["hyp"], cache[key]["secs"]
                    good, total = crit_ok(item["crit"], hyp)
                    rows.append({"lang": lang, "id": item["id"], "voice": vname, "stt": sname, "wer": wer(item["text"], hyp),
                                 "crit": good, "crit_total": total, "secs": secs, "hyp": hyp})
    write_report(rows)


def write_report(rows) -> None:
    out = WS / f"docs/bench/results-{time.strftime('%Y-%m-%d')}.md"
    lines = [f"# Voice benchmark {time.strftime('%Y-%m-%d')}", "",
             "Synthetic speech (provider TTS: Deepgram `flux-haley-en`/`flux-anjali-hi`, Gradium default EN voice), "
             "clean audio, no noise. **Not** the user's real voice: accents, noise and mic quality are untested.", "",
             "| Lang | STT | TTS voice | n | mean WER | critical tokens | mean secs/utt (incl. streaming) |",
             "|---|---|---|---|---|---|---|"]
    groups = {}
    for r in rows:
        groups.setdefault((r["lang"], r["stt"], r["voice"]), []).append(r)
    for (lang, stt, voice), rs in sorted(groups.items()):
        n = len(rs)
        w = sum(r["wer"] for r in rs) / n
        c = sum(r["crit"] for r in rs), sum(r["crit_total"] for r in rs)
        t = sum(r["secs"] for r in rs) / n
        lines.append(f"| {lang} | {stt} | {voice} | {n} | {w:.3f} | {c[0]}/{c[1]} ({100 * c[0] / max(1, c[1]):.0f}%) | {t:.2f} |")
    lines += ["", "## Worst critical-token misses", ""]
    misses = sorted((r for r in rows if r["crit"] < r["crit_total"]), key=lambda r: r["crit"] - r["crit_total"])[:15]
    for r in misses:
        lines.append(f"- {r['id']} {r['stt']}/{r['voice']}: `{r['hyp'][:110]}`")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)
    print("\n".join(lines[4:4 + len(groups) + 2]))


if __name__ == "__main__":
    asyncio.run(main())
