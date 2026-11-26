"""Benchmark recorded PCM fixtures without launching apps or playing audio."""
from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import wave
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice.events import Events
from voice.failover import Breaker, SttChain
from voice.fakes import FakeStt, FakeTts
from voice.handoff import load_handoff, settings_from_handoff
from voice.replay import ReplayFeed


async def run(args: argparse.Namespace) -> None:
    settings = settings_from_handoff(load_handoff(args.handoff))
    with wave.open(str(args.fixture), "rb") as fixture:
        if (fixture.getnchannels(), fixture.getsampwidth(), fixture.getframerate()) != (1, 2, 24000):
            raise ValueError("Fixture must be mono PCM16 WAV at 24000 Hz")
        pcm = fixture.readframes(fixture.getnframes())
    if len(pcm) > 960000 or not pcm:
        raise ValueError("Fixture must contain between one sample and 20 seconds")
    if settings.mode == "live":
        from voice.deepgram import DeepgramStt, DeepgramTts
        from voice.gradium import GradiumStt
        stt_providers = {"deepgram": DeepgramStt(settings), "gradium": GradiumStt(settings)}
        tts = DeepgramTts(settings)
    else:
        stt_providers = {"deepgram": FakeStt("What can you open?"), "gradium": FakeStt()}
        tts = FakeTts()
    with args.trace.open("w", encoding="utf-8") as output:
        events = Events(settings.mode, output)
        for _ in range(args.runs):
            utterance = str(uuid4())
            feed = ReplayFeed()
            events.emit("utterance_started", {"utterance_id": utterance})

            async def feed_audio() -> None:
                for offset in range(0, len(pcm), 960):
                    await feed.push(pcm[offset:offset + 960])
                    await asyncio.sleep(0.02)
                events.emit("speech_end", {})
                await feed.end()

            sender = asyncio.create_task(feed_audio())
            chain = SttChain(settings, stt_providers,
                             {name: Breaker() for name in stt_providers}, events.emit)
            final_text = ""
            try:
                async for result in chain.transcribe(feed):
                    if result.final:
                        final_text = result.text
                        events.emit("stt_final", {})
                await sender
                events.emit("reply_ready", {})
                first_audio = True
                async for audio in tts.stream("Okay, done." if args.language == "en" else "\u0920\u0940\u0915 \u0939\u0948\u0964", args.language):
                    if audio.pcm and first_audio:
                        events.emit("tts_first_byte", {})
                        first_audio = False
            finally:
                sender.cancel()
                await asyncio.gather(sender, return_exceptions=True)
    subprocess.run([sys.executable, "-m", "voice.latency", str(args.trace)], check=True)
    print("PROVIDER_BENCHMARK_OK")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--language", choices=["en", "hi", "hinglish"], default="en")
    args = parser.parse_args()
    if not 1 <= args.runs <= 500:
        parser.error("--runs must be between 1 and 500")
    asyncio.run(run(args))
