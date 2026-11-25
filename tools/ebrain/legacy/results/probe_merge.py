"""Agent-3 diagnostic: is the wrong-replay-head caused by cross-fact chain merge,
by a replay-rule divergence, or by silent updates landing in a fresh chain?

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_merge.py 10000 101
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
from ebrain.store import Store, CODE_RE  # noqa: E402

CANARY = {"canary", "summary", "attack", "dup"}


def main(size: int, seed: int) -> None:
    ds = generate(size, seed)
    truth = ds.truth()
    tmp = os.path.join(HERE, "_probe_tmp", f"merge_{size}_{seed}")
    os.makedirs(tmp, exist_ok=True)
    st = Store(tmp, {"heal_mode": "off"}, user_id="local")
    for ev in ds.events:
        if ev.kind == "write":
            st.write(ev.payload)

    c = Counter()
    ex = []
    for spec in ds.all_query_specs():
        if spec.qtype not in CANARY or not spec.chains:
            continue
        q = spec.query
        heads = set(truth.head_codes(spec.chains[0], q.ts))
        if not heads:
            continue
        b = st.query(q)
        shown = {code for it in b.items for code in find_codes(it.text)}
        if heads & shown:
            continue
        # find the store chain holding the true head at or before q.ts
        found_chain = None
        for code in heads:
            row = st.db.execute("SELECT chain FROM ops WHERE user_id=? AND project=? AND text LIKE ? "
                                "AND ts<=? ORDER BY ts LIMIT 1",
                                (st.u, q.project_id, f"%{code}%", q.ts)).fetchone()
            if row:
                found_chain = row["chain"]
                break
        if not found_chain:
            c["head_absent"] += 1
            continue
        # store ops in that chain (<= q.ts, visible)
        srows = st._chain_ops(q.project_id, [found_chain], q.ts, q.agent_id)
        store_ops = {r["op_id"] for r in srows}
        # true chain ops (seals) at <= q.ts
        true_ops = {o for o, s in truth.seals.items() if s.chain == spec.chains[0]
                    and o in truth.ops and truth.ops[o].ts <= q.ts
                    and (truth.ops[o].visibility == "shared"
                         or truth.ops[o].agent_id == q.agent_id)
                    and truth.ops[o].project_id == q.project_id}
        extra_in_store = store_ops - true_ops
        missing_from_store = true_ops - store_ops
        c["fail_analysed"] += 1
        if extra_in_store:
            c["has_foreign_ops_in_chain"] += 1
            # which chains do the foreign ops belong to in truth?
            foreign_chains = Counter(truth.seals[o].chain for o in extra_in_store
                                     if o in truth.seals)
            c["foreign_chains_gt1"] += int(len(foreign_chains) > 1)
        if missing_from_store:
            c["has_missing_true_ops"] += 1
        # replay heads
        h, conf, _ = st._evolve(srows)
        by_id = {r["op_id"]: r for r in srows}
        store_head_ops = h
        true_head_ops = set()
        snap = truth.snapshot(spec.chains[0], q.ts)
        if snap:
            true_head_ops = set(snap.current)
        c["store_head_eq_true_head"] += int(store_head_ops == true_head_ops)
        if len(ex) < 6 and (extra_in_store or store_head_ops != true_head_ops):
            ex.append({
                "qtext": q.text, "ts": q.ts, "true_chain": spec.chains[0],
                "found_chain": found_chain, "heads": sorted(heads),
                "n_store_ops": len(store_ops), "n_true_ops": len(true_ops),
                "n_extra": len(extra_in_store), "n_missing": len(missing_from_store),
                "foreign_chains": dict(foreign_chains),
                "store_head_ops": sorted(store_head_ops),
                "true_head_ops": sorted(true_head_ops),
            })
    st.close()
    print(f"size={size} seed={seed}")
    for k in sorted(c):
        print(f"  {k:38} {c[k]}")
    print("\nEXAMPLES:")
    for e in ex:
        print(" ", e)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
