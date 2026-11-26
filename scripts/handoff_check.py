"""Validate a local handoff without echoing credentials or provider bodies."""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from ofa_execution.config import App
from voice.contracts import SttProvider, TtsProvider
from voice.deepgram import DeepgramStt, DeepgramTts
from voice.gradium import GradiumStt, GradiumTts
from voice.handoff import load_handoff, settings_from_handoff


async def silence() -> AsyncIterator[bytes]:
    for _ in range(20):
        yield bytes(960)
        await asyncio.sleep(0.02)


async def probe_stt(provider: SttProvider) -> None:
    async with asyncio.timeout(8):
        async for _ in provider.stream(silence()):
            pass


async def probe_tts(provider: TtsProvider, language: str) -> None:
    size = 0
    text = "नमस्ते।" if language == "hi" else "Voice connection ready."
    async with asyncio.timeout(8):
        async for audio in provider.stream(text, language):
            size += len(audio.pcm)
    if size == 0:
        raise ValueError("No audio returned")


async def run(path: str, live: bool, m0_only: bool) -> int:
    errors: list[str] = []
    try:
        handoff = load_handoff(path)
        settings = settings_from_handoff(handoff)
        apps = [App.model_validate(value) for value in handoff.apps["allowlist"]]
        whatsapp = [app for app in apps if app.name.casefold() == "whatsapp"]
        if len(whatsapp) != 1:
            errors.append("WHATSAPP: select one discovered installation")
        elif getattr(whatsapp[0], "launch_kind", "exe") == "exe" and not Path(whatsapp[0].executable).is_file():
            errors.append("WHATSAPP: resolve a valid executable or registered packaged target")
    except Exception:
        print("HANDOFF: fix missing fields, invalid values or non-environment secret references")
        return 1
    probes = [
        ("Deepgram STT", probe_stt(DeepgramStt(settings))),
        ("Deepgram English TTS", probe_tts(DeepgramTts(settings), "en")),
    ] if live else []
    if live and not m0_only:
        probes.extend([
            ("Deepgram Hindi TTS", probe_tts(DeepgramTts(settings), "hi")),
            ("Gradium STT", probe_stt(GradiumStt(settings))),
            ("Gradium TTS", probe_tts(GradiumTts(settings), "en")),
        ])
    for label, coroutine in probes:
        try:
            await coroutine
            print(label + ": PROBE_OK")
        except Exception:
            errors.append(label + ": check key, credits, entitlement and network; rerun live probe")
    for error in errors:
        print(error)
    print("HANDOFF_FAILED" if errors else "HANDOFF_OK")
    if not live:
        print("LIVE_NOT_RUN")
    return int(bool(errors))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--handoff", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--m0-only", action="store_true")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.handoff, args.live, args.m0_only)))


if __name__ == "__main__":
    main()
