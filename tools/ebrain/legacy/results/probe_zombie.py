"""Agent-6 diagnostic: classify 'current' codes in bundles for a contender.

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_zombie.py <contender> 10000 101
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FINAL", "reference", "impl"))

from harness.generate import generate  # noqa: E402
from harness.truth import Truth, find_codes  # noqa: E402
from harness.metrics import evaluate_bundle, World  # noqa: E402

CANARY = {"canary", "summary", "attack", "dup"}


def load(contender):
    folder = os.path.abspath(contender)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = "pz_contender"
    spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.Adapter


def main(contender, size, seed):
    Adapter = load(os.path.join(HERE, contender))
    ds = generate(size, seed)
    truth = ds.truth()
    world = World()
    label = os.path.basename(os.path.abspath(contender))
    tmp = os.path.join(HERE, "_probe_tmp", f"zomb_{label}_{size}_{seed}")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    st = Adapter(tmp, {"seed": seed})
    for ev in ds.events:
        if ev.kind == "write":
            st.write(ev.payload)
            world.add(ev.payload)
    c = Counter()
    for spec in ds.all_query_specs():
        if spec.qtype not in CANARY or not spec.chains:
            continue
        q = spec.query
        b = st.query(q)
        ev = evaluate_bundle(b, q.agent_id, q.project_id, q.token_budget, world)
        c["queries"] += 1
        c["items"] += len(b.items)
        cur = [(it, code) for it in b.items
               if it.status == "current" and "conflict" not in it.flags
               for code in find_codes(it.text)]
        c["cur_codes"] += len(cur)
        for it, code in cur:
            s = truth.code_status(code, q.ts)
            c[f"status_{s}"] += 1
        heads = set(truth.head_codes(spec.chains[0], q.ts))
        shown = {code for it in b.items for code in find_codes(it.text)}
        c["true_cur"] += int(bool(heads & {x[1] for x in cur}))
    print(f"contender={contender} cov={os.environ.get('AG1_COVERAGE_MIN')} size={size} seed={seed}")
    for k in sorted(c):
        print(f"  {k:26} {c[k]}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
