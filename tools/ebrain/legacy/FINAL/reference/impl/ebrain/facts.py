"""Generator for ebrain/limits_facts.json: every number the UI shows comes from measured CSVs.

    python -m ebrain.facts <results_v2.csv> <ref_public_1k.csv> <ref_public_10k_101.csv> [out.json]

Sources (synthetic benchmark only):
  results_v2.csv          judge run of the frozen v2 code (contender fact-chain-graph, hash prefix
                          cb925a7aedb4103a): 1k = 3 sealed seeds; 10k = 3 sealed seeds + public 101
  ref_public_*.csv        FINAL/reference/results runs (subject-join experiment deltas)
"""
from __future__ import annotations

import csv
import json
import sys

V2 = ("fact-chain-graph", "cb925a7aedb4103a")
COPY = {
    "meter_ok": "{n} / {hard} memories — inside the tested range",
    "meter_near": "{n} / {hard} memories — close to the tested limit",
    "meter_beyond": "{n} / {hard} memories — beyond the tested range: answers are unreliable",
    "capacity_note": ("This stores your first ~1,000 memories reliably-ish. Beyond that it is "
                      "unreliable — this is a known limitation of the project as of now."),
    "experimental_badge": "EXPERIMENTAL",
    "heal_state": {"off": "Self-heal: OFF", "propose": "Self-heal: approval required",
                   "auto": "Self-heal: automatic (not recommended)"},
}
TIER = "MEASURED (synthetic sealed seeds)"
CAPS = [  # (id, can, example, scenario, metric)
    ("latest_wins", True, "Claude wrote TTL = 60 min on Monday, Codex wrote 30 min on Wednesday → "
     "you see only 30 min; the timeline lists both writes.", "S1", "correct_version_acc"),
    ("reworded_split", False, "Two agents word the same fact differently → it may show BOTH as "
     "current until you confirm.", "S1", "zombie_rate"),
    ("external_quarantine", True, "An external web page tries to overwrite a human decision → "
     "quarantined, shown only as UNTRUSTED.", "ALL", "injection_success_rate"),
    ("private_isolation", True, "Claude's private note is never shown to Codex or the voice agent.",
     "ALL", "leak_count"),
    ("same_time_conflict", False, "Claude and Codex write different values at the same moment → it "
     "should show a conflict, but sometimes shows one value as current.", "ALL", "conflict_acc"),
    ("rollback", True, "Undo everything after Tuesday 10:00 → the brain answers exactly as it did "
     "then.", "S11", "rollback_exact"),
    ("ambiguous_question", False, "\"What's the TTL?\" when there are three TTLs → you may get only "
     "some of them.", "ALL", "ambiguous_recall"),
]
FLAWS = [  # (id, text, scenario, metric)
    ("split_chains", "Reworded updates can leave the old value marked current.", "ALL", "zombie_rate"),
    ("recall_at_scale", "Above 1,000 memories it finds the current value much less often.", "ALL",
     "correct_version_acc"),
    ("heal_harm", "Automatic self-heal hid correct memories in tests, so it needs your approval.",
     "ALL", "heal_harm_rate"),
]


def _rows(path: str) -> list[dict]:
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _rng(vals: list[float]) -> str:
    lo, hi = min(vals), max(vals)
    return f"{lo:.2f}" if f"{lo:.2f}" == f"{hi:.2f}" else f"{lo:.2f}–{hi:.2f}"


def _pick(rows: list[dict], size: int, scen: str, metric: str) -> list[float]:
    return [float(r["value"]) for r in rows if r["contender"] == V2[0]
            and r["code_hash"].startswith(V2[1]) and int(r["size"]) == size
            and r["scenario"] == scen and r["metric"] == metric]


def _ref(rows: list[dict], contender: str, metric: str) -> list[float]:
    return [float(r["value"]) for r in sorted(rows, key=lambda r: int(r["seed"]))
            if r["contender"] == contender and r["scenario"] == "ALL" and r["metric"] == metric]


def build(results_v2: str, ref_1k: str, ref_10k: str) -> dict:
    v2, r1, r10 = _rows(results_v2), _rows(ref_1k), _rows(ref_10k)
    caps = [{"id": i, "can": c, "example": e, "tier": TIER, "metric": f"{s} {m}" if s != "ALL" else m,
             "at_1k": _rng(_pick(v2, 1000, s, m)), "at_10k": _rng(_pick(v2, 10000, s, m))}
            for i, c, e, s, m in CAPS]
    flaws = [{"id": i, "text": t, "metric": m, "at_1k": _rng(_pick(v2, 1000, s, m)),
              "at_10k": _rng(_pick(v2, 10000, s, m))} for i, t, s, m in FLAWS]

    def delta(rows: list[dict], var: str) -> str:
        d = [a - b for a, b in zip(_ref(rows, var, "zombie_rate"), _ref(rows, V2[0], "zombie_rate"))]
        return f"{max(d, key=abs):+.3f}"
    flaws.append({"id": "subject_join_experiment",
                  "text": "The experimental same-fact detector did not reduce stale values in tests "
                          "and is OFF.", "metric": "zombie_rate change vs v2 (public seeds)",
                  "at_1k": delta(r1, "ebrain-ref-join_on_heal_auto"),
                  "at_10k": delta(r10, "ebrain-ref-join_on_heal_auto")})
    return {"schema_version": 1, "experimental": True, "copy": COPY, "capabilities": caps,
            "known_flaws": flaws,
            "measured_source": "Synthetic benchmark only: judge/results_summary.md (sealed seeds "
                               "556920, 878791, 235664; 10k adds public 101) and "
                               "FINAL/reference/results (public seeds 101–103)."}


if __name__ == "__main__":
    out = build(sys.argv[1], sys.argv[2], sys.argv[3])
    text = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if len(sys.argv) > 4:
        with open(sys.argv[4], "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
