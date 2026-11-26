"""python -m voice.latency traces.jsonl; missing stages remain unmeasured."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("No measurements")
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]


def main() -> None:
    parser = argparse.ArgumentParser(prog="voice-latency-report")
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    turns: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for line in args.trace.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("utterance_id"):
            key = (event.get("mode", "unknown"), event["utterance_id"])
            turns[key].setdefault(event["type"], event["monotonic_ns"])
    stages = {
        "stt_interim": ("utterance_started", "stt_first_event"),
        "stt_final": ("speech_end", "stt_final"),
        "launch_dispatch": ("speech_end", "launch_dispatch"),
        "ack_start": ("launch_verified", "ack_first_sample"),
        "llm_first_token": ("stt_final", "llm_first_token"),
        "tts_first_byte": ("reply_ready", "tts_first_byte"),
        "audible_reply": ("speech_end", "playback_first_sample"),
        "barge_in": ("barge_detected", "playback_silent"),
        "failover": ("provider_failed", "fallback_first_audio"),
    }
    print("mode stage n p50_ms p95_ms")
    modes = sorted({mode for mode, _ in turns}) or ["unknown"]
    for mode in modes:
        for stage, (start, end) in stages.items():
            values = [(events[end] - events[start]) / 1e6
                      for (item_mode, _), events in turns.items()
                      if item_mode == mode and start in events and end in events
                      and events[end] >= events[start]]
            if values:
                print(f"{mode} {stage} {len(values)} "
                      f"{percentile(values, .5):.1f} {percentile(values, .95):.1f}")
            else:
                print(f"{mode} {stage} 0 NOT_MEASURED NOT_MEASURED")


if __name__ == "__main__":
    main()
