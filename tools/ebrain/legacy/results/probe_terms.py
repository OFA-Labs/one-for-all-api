"""Agent-4 diagnostic: term-signature structure of true chains vs near-miss chains.

Run from benchmark/:  .venv\\Scripts\\python.exe ..\\results\\probe_terms.py 10000 101
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "FINAL", "reference", "impl"))

from harness.generate import generate  # noqa: E402
from harness.truth import find_codes  # noqa: E402
from ebrain.store import CODE_RE, _terms  # noqa: E402


def main(size: int, seed: int) -> None:
    ds = generate(size, seed)
    # group version/copy ops by true chain
    by_chain = defaultdict(list)
    for w in ds.writes:
        seal = ds.seals.get(w.op_id)
        if seal is None or seal.role not in ("version", "copy"):
            continue
        ts = _terms(w.text, w.path)
        if ts:
            by_chain[seal.chain].append((w, seal, ts))

    core_shared = Counter()
    alias_var = Counter()
    # for each chain, intersection of all version term sets
    inter_stats = Counter()
    chain_cores = {}
    for cid, items in by_chain.items():
        vers = [ts for w, s, ts in items if s.role == "version"]
        if not vers:
            continue
        union = set().union(*vers)
        inter = set.intersection(*vers)
        chain_cores[cid] = union
        inter_stats["chains"] += 1
        inter_stats["inter_size"] += len(inter)
        inter_stats[f"inter_{min(len(inter), 6)}"] += 1
        # per-version: does it share >=2 and >=1 distinctive (not in global-common)?
        for ts in vers:
            alias_var["versions"] += 1
            alias_var["shared_ge2"] += int(len(ts & union) >= 2)
            alias_var["shared_ge3"] += int(len(ts & union) >= 3)
            alias_var["contained_in_union"] += int(ts <= union)

    # near-miss pairs: chains with same subject group (from chain meta)
    meta = ds.chains
    pairs = Counter()
    cids = list(chain_cores)
    for i, a in enumerate(cids):
        ma = meta.get(a)
        if not ma:
            continue
        for b in cids[i + 1:]:
            mb = meta.get(b)
            if not mb:
                continue
            # same fact, different scope, same project => near miss
            if ma.subject.fact.key == mb.subject.fact.key and ma.project == mb.project:
                A, B = chain_cores[a], chain_cores[b]
                shared = len(A & B)
                pairs["pairs"] += 1
                pairs[f"shared_{min(shared, 8)}"] += 1
                # do they differ by exactly a scope token?
                pairs["diff_le2"] += int(len(A ^ B) <= 2)

    print(f"size={size} seed={seed}")
    print("chain intersection of all version term sets:", dict(inter_stats))
    print("per-version sharing with chain union:", dict(alias_var))
    print("near-miss (same fact+project, diff scope) term overlap:", dict(pairs))

    # show a couple of near-miss core pairs
    shown = 0
    for a in cids:
        ma = meta.get(a)
        if not ma:
            continue
        for b in cids:
            mb = meta.get(b)
            if a >= b or not mb:
                continue
            if ma.subject.fact.key == mb.subject.fact.key and ma.project == mb.project:
                print(f"  {ma.subject.name.__name__} {ma.subject.fact.key} "
                      f"scope={ma.subject.slug!r} vs {mb.subject.slug!r}: "
                      f"A={sorted(chain_cores[a])} B={sorted(chain_cores[b])}")
                shown += 1
                if shown >= 5:
                    return


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]))
