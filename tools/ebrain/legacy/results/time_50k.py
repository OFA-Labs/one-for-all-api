"""Agent-1 timing probe (EXPERIMENT ONLY): time dataset generation at scale."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "benchmark"))
import run_extended as ext  # applies the catalogue patch

from harness.generate import generate

for size in (10000, 20000, 50000):
    t0 = time.monotonic()
    ds = generate(size, 101)
    dt = time.monotonic() - t0
    print(f"size={size} gen_s={dt:.1f} writes={len(ds.writes)} "
          f"events={len(ds.events)} chains={len(ds.chains)}", flush=True)
