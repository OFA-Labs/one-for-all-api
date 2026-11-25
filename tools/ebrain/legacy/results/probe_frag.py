"""Agent-5 diagnostic: chain fragmentation / pollution for a given contender.

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_frag.py <contender-dir> 10000 101
"""
from __future__ import annotations

import importlib.util
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FINAL", "reference", "impl"))

from harness.generate import generate  # noqa: E402
from harness.truth import find_codes  # noqa: E402


def load(contender):
    folder = os.path.abspath(contender)
    if folder not in sys.path:
        sys.path.insert(0, folder)
    name = "probe_contender"
    spec = importlib.util.spec_from_file_location(name, os.path.join(folder, "adapter.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod.Adapter


def main(contender, size, seed):
    Adapter = load(os.path.join(HERE, contender))
    ds = generate(size, seed)
    truth = ds.truth()
    import shutil
    label = os.path.basename(os.path.abspath(contender))
    tmp = os.path.join(HERE, "_probe_tmp", f"frag_{label}_{size}_{seed}")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    st = Adapter(tmp, {"seed": seed})
    for ev in ds.events:
        if ev.kind == "write":
            st.write(ev.payload)

    # map store chain -> set of true chains
    sc = defaultdict(Counter)
    for row in st.db.execute("SELECT chain, text FROM ops WHERE user_id=? AND chain IS NOT NULL",
                             (st.u,)):
        for code in find_codes(row["text"]):
            info = truth.code_info.get(code)
            if info:
                sc[row["chain"]][info[0]] += 1
    c = Counter()
    c["true_chains"] = len({s.chain for s in ds.seals.values() if s.chain.startswith("chain-")})
    c["store_chains"] = len(sc)
    for chain, tc in sc.items():
        c["chains_with_codes"] += 1
        c["pure"] += int(len(tc) == 1)
        c["mixed"] += int(len(tc) > 1)
        if len(tc) > 1:
            c["mixed_chains_ops"] += sum(tc.values())
    print(f"contender={contender} size={size} seed={seed}")
    for k in sorted(c):
        print(f"  {k:28} {c[k]}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
