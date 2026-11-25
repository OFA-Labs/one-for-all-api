"""Agent-1 EXTENDED-CATALOGUE harness driver (EXPERIMENT ONLY, not product code).

The frozen generator exhausts its subject catalogue at 50k
(scenarios.py:287, 36 facts x 9 scopes x 2 projects = 648 subjects, but
size//20 = 2500 chains are needed). This script monkeypatches ONLY the
subject catalogue at runtime -- no file under benchmark/ or FINAL/ is edited --
adding explicitly labelled extra scopes so a 50k dataset can be built and
scored. The extension is recorded in every result CSV's `note` column.

Run from benchmark/:
  .venv\\Scripts\\python.exe ..\\results\\run_extended.py <contender> <size> <seed> <out.csv> [timeout_s]
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = os.path.join(os.path.dirname(HERE), "benchmark")
sys.path.insert(0, BENCH)

from harness import generate as gen  # noqa: E402
from harness import scenarios as scen  # noqa: E402
from harness import runner  # noqa: E402

ORIGINAL_SCOPES = list(gen.SCOPES)
EXTRA_SCOPES = []
for _i in range(1, 11):
    EXTRA_SCOPES += [
        (f"for team t{_i:02d}", f"team-t{_i:02d}"),
        (f"in region r{_i:02d}", f"region-r{_i:02d}"),
        (f"for customer c{_i:02d}", f"customer-c{_i:02d}"),
        (f"in release v{_i:02d}", f"release-v{_i:02d}"),
        (f"for environment e{_i:02d}", f"env-e{_i:02d}"),
    ]


def extended_subjects():
    scopes = ORIGINAL_SCOPES + EXTRA_SCOPES
    return [gen.Subject(f, s, slug) for f in gen.FACTS for s, slug in scopes]


# patch both namespaces: scenarios imported all_subjects by name
scen.all_subjects = extended_subjects
gen.all_subjects = extended_subjects


def main() -> None:
    contender, size, seed, out = sys.argv[1:5]
    timeout = float(sys.argv[5]) if len(sys.argv) > 5 else 1800.0
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    print(f"EXTENDED CATALOGUE: {len(gen.FACTS)} facts x "
          f"{len(ORIGINAL_SCOPES) + len(EXTRA_SCOPES)} scopes x 2 projects = "
          f"{len(extended_subjects())} subjects "
          f"(frozen catalogue was {len(gen.FACTS) * len(ORIGINAL_SCOPES) * 2})")
    run = runner.Run(contender, int(size), int(seed), timeout)
    rows = run.run()
    rows.append(runner.MetricRow(
        "ALL", "extended_catalogue", 1, 1, "bool",
        f"50k-only runtime patch in results/run_extended.py; "
        f"{len(EXTRA_SCOPES)} extra scopes; frozen benchmark NOT modified"))
    runner.append_csv(out, run, rows)
    print(f"{run.name} size={run.size} seed={run.seed} hash={run.hash[:12]}")
    for r in rows:
        if r.scenario == "ALL" and r.metric in (
                "correct_version_acc", "zombie_rate", "tokens_mean", "tokens_p95",
                "budget_violations", "injection_success_rate", "leak_count",
                "query_p95_ms", "crashes", "runtime_s"):
            print(f"  {r.metric:26} {r.value!s:>10}  n={r.n}")


if __name__ == "__main__":
    main()
