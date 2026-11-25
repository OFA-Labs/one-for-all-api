"""Agent-1 diagnostic probe (EXPERIMENT ONLY, not product code).

Replays a harness dataset into the shipped Store and classifies each canary
bundle: was the true chain retrieved, how many chains were shown, and what
status the sealed truth assigns to every "current" code in the bundle.

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_diag.py 10000 101
"""
from __future__ import annotations

import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FINAL", "reference", "impl"))

from harness.generate import generate  # noqa: E402
from harness.truth import Truth, find_codes  # noqa: E402
from harness.metrics import evaluate_bundle, World  # noqa: E402
from harness.api import Query  # noqa: E402
from ebrain.store import Store  # noqa: E402

CANARY = {"canary", "summary", "attack", "dup"}


def main(size: int, seed: int) -> None:
    ds = generate(size, seed)
    truth = ds.truth()
    world = World()
    tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_probe_tmp", f"{size}_{seed}")
    os.makedirs(tmp, exist_ok=True)
    st = Store(tmp, {"heal_mode": "off"}, user_id="local")

    # replay writes in stream order (ignore non-write events)
    for ev in ds.events:
        if ev.kind == "write":
            st.write(ev.payload)
            world.add(ev.payload)

    stats = Counter()
    examples = []
    for spec in ds.all_query_specs():
        if spec.qtype not in CANARY or not spec.chains:
            continue
        q = spec.query
        b = st.query(q)
        ev = evaluate_bundle(b, q.agent_id, q.project_id, q.token_budget, world)
        chain = spec.chains[0]
        heads = set(truth.head_codes(chain, q.ts))
        codes_in_bundle = {c for it in b.items for c in find_codes(it.text)}
        codes_cur = {c for it in b.items if it.status == "current" and "conflict" not in it.flags
                     for c in find_codes(it.text)}
        true_in = bool(heads & codes_in_bundle)
        true_cur = bool(heads & codes_cur)
        stats["n"] += 1
        stats["true_cur"] += int(true_cur)
        stats["true_in_bundle_not_cur"] += int(true_in and not true_cur)
        stats["chains_shown"] += len(b.items)
        # classify current codes
        for c in codes_cur:
            s = truth.code_status(c, q.ts)
            stats[f"cur_{s}"] += 1
            cinfo = truth.code_info.get(c)
            own = bool(cinfo and cinfo[0] == chain)
            stats[f"cur_{s}_{'own' if own else 'other'}"] += 1
        if not true_cur and len(examples) < 6:
            examples.append({
                "qid": q.query_id, "qtext": q.text, "ts": q.ts,
                "chain": chain, "heads": sorted(heads),
                "bundle_codes": sorted(codes_in_bundle),
                "cur_codes": sorted(codes_cur),
                "cur_status": {c: truth.code_status(c, q.ts) for c in codes_cur},
            })
    st.close()
    print(f"size={size} seed={seed}  n_canary={stats['n']}")
    for k in sorted(stats):
        if k != "n":
            v = stats[k]
            if k.startswith("chains_shown"):
                v = round(v / stats["n"], 2)
            print(f"  {k:42} {v}")
    print("\nEXAMPLES where true head not current:")
    for e in examples:
        print(" ", e)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
