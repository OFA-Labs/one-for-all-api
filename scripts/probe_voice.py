"""Real provider probes using synthetic audio. No microphone, apps or playback."""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice.config import Settings
from voice.deepgram import DeepgramStt, DeepgramTts
from voice.gradium import GradiumStt, GradiumTts


async def run():
    settings = Settings.from_env()
    async def synth(provider, text, language):
        async with asyncio.timeout(20):
            chunks = [chunk.pcm async for chunk in provider.stream(text, language)]
        pcm = b"".join(chunks)
        if not pcm or len(pcm) % 2:
            raise ValueError("Invalid PCM")
        return pcm
    sample = None
    results = []
    for name, provider, text, language in [
        ("deepgram_tts_en", DeepgramTts(settings), "Open WhatsApp.", "en"),
        ("deepgram_tts_hi", DeepgramTts(settings), "व्हाट्सऐप खोलो।", "hi"),
        ("gradium_tts_en", GradiumTts(settings), "Voice connection ready.", "en")]:
        began = time.monotonic()
        try:
            pcm = await synth(provider, text, language)
            if name == "deepgram_tts_en": sample = pcm
            results.append(dict(probe=name, result="PASS", pcm_bytes=len(pcm),
                                duration_s=round(time.monotonic()-began, 3)))
        except Exception as error:
            status = getattr(getattr(error, "response", None), "status_code", None)
            results.append(dict(probe=name, result="FAIL", error_type=type(error).__name__, http_status=status))
    if sample:
        async def frames():
            pcm = sample + bytes(24000)
            for offset in range(0, len(pcm), 960):
                yield pcm[offset:offset+960]
                await asyncio.sleep(0.02)
        for name, provider in [("deepgram_stt", DeepgramStt(settings)), ("gradium_stt", GradiumStt(settings))]:
            try:
                async with asyncio.timeout(20):
                    finals = [r.text async for r in provider.stream(frames()) if r.final]
                results.append(dict(probe=name, result="PASS" if any(finals) else "FAIL", synthetic_transcript=finals))
            except Exception as error:
                status = getattr(getattr(error, "response", None), "status_code", None)
                results.append(dict(probe=name, result="FAIL", error_type=type(error).__name__, http_status=status))
    print(json.dumps({"kind": "live_provider_synthetic_audio", "microphone_used": False,
                      "results": results}, indent=2, ensure_ascii=False))
    return int(any(row["result"] != "PASS" for row in results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    args = parser.parse_args()
    if args.env_file:
        from dotenv import load_dotenv
        load_dotenv(args.env_file, override=False)
    raise SystemExit(asyncio.run(run()))
