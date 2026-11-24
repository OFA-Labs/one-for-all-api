"""T-024: ebrain/limits_facts.json equals the generator output from the measured CSVs.

In the tournament tree the CSVs are found relative to this file; elsewhere set EBRAIN_FACTS_SOURCES
to "<results_v2.csv>;<ref_public_1k.csv>;<ref_public_10k_101.csv>". If neither is available (the
one-for-all-api repo), only the JSON shape is checked.
"""
import json
import os

from conftest import ROOT
from ebrain.facts import build

FACTS = os.path.join(ROOT, "ebrain", "limits_facts.json")
_T = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))  # tournament root when ROOT=FINAL/reference/impl
DEFAULT_SOURCES = (os.path.join(_T, "benchmark", "results_v2.csv"),
                   os.path.join(_T, "FINAL", "reference", "results", "public_1k.csv"),
                   os.path.join(_T, "FINAL", "reference", "results", "public_10k_101.csv"))


def _load():
    with open(FACTS, encoding="utf-8") as f:
        return json.load(f)


def test_T024_facts_shape():
    d = _load()
    assert d["schema_version"] == 1 and d["experimental"] is True
    for row in d["capabilities"]:
        assert {"id", "can", "example", "tier", "metric", "at_1k", "at_10k"} <= set(row)
    assert {r["id"] for r in d["known_flaws"]} >= {"split_chains", "recall_at_scale", "heal_harm"}
    assert "~1,000 memories" in d["copy"]["capacity_note"]


def test_T024_facts_match_measured_csvs():
    env = os.environ.get("EBRAIN_FACTS_SOURCES")
    sources = env.split(";") if env else DEFAULT_SOURCES
    if not all(os.path.isfile(p) for p in sources):
        import pytest
        pytest.skip("measured CSVs not present in this checkout")
    assert build(*sources) == _load()
