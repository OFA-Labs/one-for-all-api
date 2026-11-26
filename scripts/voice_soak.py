"""Thirty-minute synthetic task/memory soak; never certifies live audio quality."""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from voice.config import Settings
from voice.failover import Breaker, SttChain
from voice.fakes import FakeStt
from voice.replay import ReplayFeed


async def run(seconds: float) -> None:
    tracemalloc.start()
    baseline_tasks = len(asyncio.all_tasks())
    baseline_memory = None
    end = time.monotonic() + seconds
    runs = 0
    while time.monotonic() < end:
        feed = ReplayFeed()
        await feed.push(bytes(960))
        await feed.end()
        chain = SttChain(Settings(), {"deepgram": FakeStt(), "gradium": FakeStt()},
                         {"deepgram": Breaker(), "gradium": Breaker()},
                         lambda kind, payload: None)
        results = [value async for value in chain.transcribe(feed)]
        assert sum(result.final for result in results) == 1
        assert len(asyncio.all_tasks()) <= baseline_tasks + 1
        runs += 1
        current, _ = tracemalloc.get_traced_memory()
        if runs == 100:
            baseline_memory = current
        if baseline_memory is not None:
            assert current < baseline_memory + 2_000_000
        await asyncio.sleep(0.02)
    print(f"FAKE_SOAK_OK runs={runs} duration_s={seconds:.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=1800)
    arguments = parser.parse_args()
    asyncio.run(run(arguments.seconds))
