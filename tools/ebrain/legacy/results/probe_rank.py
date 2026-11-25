"""Agent-2 diagnostic: for failing canary queries, locate the true head code in
the store and check whether its chain is assembled and/or ranked.

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_rank.py 10000 101
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
from ebrain.store import Store, _terms  # noqa: E402

CANARY = {"canary", "summary", "attack", "dup"}


def main(size: int, seed: int) -> None:
    ds = generate(size, seed)
    truth = ds.truth()
    tmp = os.path.join(HERE, "_probe_tmp", f"rank_{size}_{seed}")
    os.makedirs(tmp, exist_ok=True)
    st = Store(tmp, {"heal_mode": "off"}, user_id="local")
    for ev in ds.events:
        if ev.kind == "write":
            st.write(ev.payload)

    c = Counter()
    examples = []
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
            c["ok"] += 1
            continue
        c["fail"] += 1
        # locate true head codes in the store
        loc = {}
        for code in heads:
            row = st.db.execute("SELECT chain, ts, role FROM ops WHERE user_id=? AND project=? "
                                "AND text LIKE ? AND ts<=? ORDER BY ts",
                                (st.u, q.project_id, f"%{code}%", q.ts)).fetchall()
            loc[code] = [(r["chain"], r["ts"], r["role"]) for r in row]
        # what did _rank return, and is any located chain in it?
        ranked = st._rank(q, q.ts)
        located_chains = {ch for v in loc.values() for ch, _, _ in v}
        c["head_present_in_store"] += int(bool(located_chains))
        c["head_chain_in_top_rank"] += int(bool(located_chains & set(ranked)))
        c["head_chain_but_not_bundle"] += int(bool(located_chains & set(ranked)) and False)
        # is the head the replay head of its store chain?
        head_is_store_head = False
        for code, rows in loc.items():
            for ch, _, _ in rows:
                op_rows = st._chain_ops(q.project_id, [ch], q.ts, q.agent_id)
                h, _conf, _ = st._evolve(op_rows)
                by_id = {r["op_id"]: r for r in op_rows}
                for oid in h:
                    if code in find_codes(by_id[oid]["text"]):
                        head_is_store_head = True
        c["head_is_store_head"] += int(head_is_store_head)
        c[f"n_located_{len(located_chains)}"] += 1
        if len(examples) < 8:
            examples.append({
                "qtext": q.text, "true_chain": spec.chains[0], "heads": sorted(heads),
                "loc": {k: v[:4] for k, v in loc.items()},
                "ranked": ranked, "n_ranked": len(ranked),
                "head_is_store_head": head_is_store_head,
            })
    st.close()
    print(f"size={size} seed={seed} canary n={c['ok']+c['fail']}")
    for k in sorted(c):
        print(f"  {k:40} {c[k]}")
    print("\nEXAMPLES:")
    for e in examples:
        print(" ", e)


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
