"""Mechanical scorer for judge/anchors.md v1.0 over benchmark/results_v2.csv.

Runs (anchors §0.3): sealed seeds 556920, 878791, 235664 at 1k and 10k; public
seed 101 is not a scoring run. Share metrics = mean over runs; @10k = mean of
the 10k runs; latency = median over the 10k runs. A run the contender timed out
(run_status UNMEASURED) makes every component that needs it score 0 (§0.3).
Checklist points (V, X, K, J, Q, E) are judge inputs recorded in scorecard.md.
"""
import csv, math, statistics as st
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAB = {"control": "Control", "event-fold": "Spec-X", "fact-chain-graph": "Spec-Y", "lifecycle-ledger": "Spec-Z"}
D = defaultdict(dict)  # D[label][(size, seed, scen, metric)] = value
TOUT = defaultdict(set)
NAN = float("nan")
for r in csv.DictReader(open(ROOT / "benchmark" / "results_v2.csv", encoding="utf-8")):
    if r["metric"] == "run_status" and r["value"] == "UNMEASURED":
        TOUT[LAB[r["contender"]]].add((int(r["size"]), int(r["seed"])))
    try: v = float(r["value"])
    except ValueError: continue
    D[LAB[r["contender"]]][(int(r["size"]), int(r["seed"]), r["scenario"], r["metric"])] = v
SEALED = (556920, 878791, 235664)
ONE = [(1000, sd) for sd in SEALED]; TEN = [(10000, sd) for sd in SEALED]
RUNS = ONE + TEN

def m(c, scen, met, runs=RUNS):
    if any(r in TOUT[c] for r in runs): return NAN
    vals = [D[c][(s, sd, scen, met)] for s, sd in runs if (s, sd, scen, met) in D[c]]
    return st.mean(vals) if vals else NAN

def scale(pts):  # pts: list of (value, score) sorted by value
    def f(x):
        if math.isnan(x): return NAN
        if x <= pts[0][0]: return pts[0][1]
        if x >= pts[-1][0]: return pts[-1][1]
        for (x0, s0), (x1, s1) in zip(pts, pts[1:]):
            if x0 <= x <= x1: return s0 + (s1 - s0) * (x - x0) / (x1 - x0)
    return f
up = lambda *v: scale(list(zip(v, (0, 2, 4, 6, 8, 10))))
dn = lambda *v: scale(list(zip(v[::-1], (10, 8, 6, 4, 2, 0))))
ACC = up(.40, .55, .70, .80, .90, .97); REC = up(.20, .40, .55, .70, .85, .95)
ZOM = dn(.35, .20, .10, .05, .02, 0); HARM = dn(.20, .10, .06, .03, .01, 0)
INJ = dn(.30, .15, .07, .03, .01, 0); PROV = up(.70, .85, .93, .97, .99, .999)
TPC = dn(1000, 700, 450, 250, 120, 60); QP95 = dn(1500, 500, 200, 100, 50, 25)
QP50 = dn(600, 200, 80, 40, 20, 10); WP95 = dn(1000, 300, 100, 40, 15, 5)
MP95 = dn(180000, 60000, 15000, 5000, 2000, 500)
g = lambda a: NAN if math.isnan(a) else min(1.0, a / 0.50)
W = {"P1": 15, "P2": 10, "P3": 8, "P4": 12, "P5": 15, "P6": 10, "P7": 10, "P8": 2, "P9": 5, "P10": 8, "P11": 5}
CHK = {  # judge checklist inputs (see scorecard.md)
    "Control": dict(V=0, B7=2.5, X=0, K=5.2, J=2.8, Q=6.67, E=9.0),
    "Spec-X": dict(V=5.0, B7=10, X=6.8, K=5.0, J=6.3, Q=8.0, E=9.0),
    "Spec-Y": dict(V=5.0, B7=10, X=6.8, K=5.0, J=6.3, Q=8.0, E=9.0),
    "Spec-Z": dict(V=4.5, B7=9.5, X=6.8, K=5.0, J=6.3, Q=8.0, E=9.0),
}
def lat(c, met):
    if any(r in TOUT[c] for r in TEN): return NAN
    return st.median(D[c][(s, sd, "ALL", met)] for s, sd in TEN)

def p8(c):  # step table, cumulative levels, odd = L + one condition of L+2
    if any(r in TOUT[c] for r in TEN): return 0
    a1, a10 = m(c, "ALL", "correct_version_acc", ONE), m(c, "ALL", "correct_version_acc", TEN)
    r = lat(c, "query_p95_ms") / st.median(D[c][(s, sd, "ALL", "query_p95_ms")] for s, sd in ONE)
    T = max(D[c][(s, sd, "ALL", "runtime_s")] for s, sd in TEN)
    lv = {4: [T < 900, a10 >= a1 - .12, r <= 15], 6: [a10 >= a1 - .06, r <= 6], 8: [T < 300, a10 >= a1 - .03, r <= 3]}
    L = 2
    for k in (4, 6, 8):
        if all(lv[k]): L = k
        else: break
    nxt = lv.get(L + 2, [])
    return (L + 1 if any(nxt) else L) * g(a10), (round(a1, 3), round(a10, 3), round(r, 1), T)

out = {}
for c in ["Control", "Spec-X", "Spec-Y", "Spec-Z"]:
    k = CHK[c]; comp = {}
    s1, s3, s7 = m(c, "S1", "correct_version_acc"), m(c, "S3", "correct_version_acc"), m(c, "S7", "correct_version_acc", TEN)
    comp["P1.A"] = (.50, ACC(st.mean([s1, s3, s7])), True)
    comp["P1.B"] = (.25, REC(m(c, "ALL", "ambiguous_recall")), True)
    comp["P1.C"] = (.25, ACC(st.mean([m(c, "S6", "correct_version_acc"), m(c, "S10", "correct_version_acc")])), True)
    pooled = m(c, "ALL", "correct_version_acc")
    comp["P2.A"] = (.40, REC(st.mean([m(c, "S9", "correct_version_acc_b64"), m(c, "S9", "correct_version_acc_b256")])), True)
    comp["P2.B"] = (.30, TPC(m(c, "ALL", "tokens_mean") / max(m(c, "S9", "correct_version_acc_b1024"), .05)), True)
    comp["P2.C"] = (.20, ZOM(m(c, "S3", "dup_item_rate")) * g(s3), True)
    comp["P2.D"] = (.10, (10 if m(c, "ALL", "budget_violations") == 0 else 0) * g(pooled), True)
    g7 = g(s7)
    comp["P3.A"] = (.45, QP95(lat(c, "query_p95_ms")) * g7, True)
    comp["P3.B"] = (.20, QP50(lat(c, "query_p50_ms")) * g7, True)
    comp["P3.C"] = (.20, WP95(lat(c, "write_p95_ms")) * g7, True)
    comp["P3.D"] = (.15, MP95(lat(c, "maintain_p95_ms")) * g7, True)
    comp["P4.F"] = (.40, ZOM(m(c, "S1", "zombie_rate")) * g(s1), True)
    comp["P4.V"] = (.60, k["V"], False)
    rec = m(c, "ALL", "stale_demotion_recall")
    comp["P5.A"] = (.40, REC(rec), True)
    comp["P5.B"] = (.35, HARM(m(c, "ALL", "heal_harm_rate")) * min(1, rec / .5), True)
    comp["P5.C"] = (.15, ZOM(m(c, "S10", "zombie_rate")) * g(m(c, "S10", "correct_version_acc")), True)
    comp["P5.D"] = (.10, 10 * m(c, "S11", "rollback_exact"), True)
    comp["P6.A"] = (.25, ZOM(st.mean([m(c, "S4", "tombstone_zombie_rate"), m(c, "S7", "zombie_rate", TEN)])) * g7, True)
    comp["P6.B"] = (.25, ACC(m(c, "ALL", "conflict_acc")), True)
    comp["P6.C"] = (.15, PROV(m(c, "ALL", "provenance_valid")) * g(pooled), True)
    comp["P6.D"] = (.20, ACC(m(c, "ALL", "asof_acc")), True)
    comp["P6.E"] = (.15, k["E"], True)
    g6 = g(m(c, "S6", "correct_version_acc"))
    comp["P7.A"] = (.50, INJ(m(c, "ALL", "injection_success_rate")) * g6, True)
    comp["P7.B"] = (.20, k["B7"] * g6, True)
    comp["P7.C"] = (.30, k["X"], False)
    p = p8(c); comp["P8"] = (1, p[0] if isinstance(p, tuple) else p, True); print("  P8 inputs", p); comp["P9"] = (1, k["K"], False)
    comp["P10"] = (1, k["J"], False); comp["P11"] = (1, k["Q"], False)
    P = defaultdict(float)
    for name, (sh, s, h) in comp.items(): P[name.split(".")[0]] += sh * s
    final = sum(P[p] * W[p] for p in W) / 10
    comp = {n: (sh, 0.0 if math.isnan(s) else s, h) for n, (sh, s, h) in comp.items()}
    P = defaultdict(float)
    for name, (sh, s, h) in comp.items(): P[name.split(".")[0]] += sh * s
    final = sum(P[p] * W[p] for p in W) / 10
    hw = [(W[n.split(".")[0]] * sh, s) for n, (sh, s, h) in comp.items() if h]
    mc = 100 * sum(w * s for w, s in hw) / sum(w * 10 for w, s in hw)
    arg = {"Spec-X": (5.0, 2.0, 3.0, 3.5), "Spec-Y": (5.0, 2.0, 3.0, 3.5), "Spec-Z": (4.5, 2.0, 3.0, 3.5)}.get(c, (0, 0, 0, 0))
    noarg = final - (0.6 * arg[0] * 12 + 0.3 * arg[1] * 10 + arg[2] * 5 + arg[3] * 8) / 10  # ARGUED credit removed (§7.4b)
    print(f"  Final without ARGUED = {noarg:.2f}")
    out[c] = (comp, P, final, mc)
    print(f"\n## {c}  Final={final:.2f}  MC={mc:.2f}")
    for p in W: print(f"  {p:4} {P[p]:5.2f}")
    for n, (sh, s, h) in comp.items(): print(f"    {n:5} share={sh:.2f} s={s:5.2f}")
