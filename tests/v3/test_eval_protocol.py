"""Executable M7 evaluation-protocol cases (H05, M04, EV-*).

Every test in this file is mandatory: no skips, no product imports, no
external services. All data is synthetic and deterministic.
"""
from __future__ import annotations

import ast
import json
import os
import re
import sys

import pytest

from tools.ebrain.v3_eval import cli, generator, manifest, metrics, oracle, runner

DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def _write_json(path, obj) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, sort_keys=True)


# ------------------------------------------------------------------- H05
def test_h05_true_plus_zombie_and_all_empty_both_fail(miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    base = metrics.correct_answer(expected, query_id="q-mini",
                                  scenario="sequential")
    assert metrics.gate(base, expected)["gate_pass"] is True

    rows, results = metrics.evaluate_negative_controls(
        base, expected, ["true_plus_zombie", "empty"])
    by_name = {r.name: r for r in results}
    assert set(by_name) == {"true_plus_zombie", "empty"}

    zombie = by_name["true_plus_zombie"]
    assert zombie.detectors["zombie"] is True
    assert zombie.gate["joint_exact"] is False
    assert zombie.correctly_failed is True

    empty = by_name["empty"]
    assert empty.detectors["all_abstain"] is True
    assert empty.gate["joint_exact"] is False
    assert empty.correctly_failed is True

    # Legacy presence is reported separately and never rescues either answer.
    empty_answer = metrics.make_control("empty", base, expected)
    presence = metrics.legacy_presence(empty_answer, expected)
    assert presence.value == 0.0
    assert presence.n == len(expected.current_set)
    assert metrics.joint_exact(empty_answer, expected) is False
    assert all(r.n == 1 for r in rows)


# --------------------------------------------------------- M04 generator
@pytest.mark.m04_100k
def test_m04_generator_100k_events_and_100k_distinct_keys():
    ev_stats = generator.stream_stats(101, 100_000, "event_count")
    assert ev_stats["event_count"] == 100_000
    assert DIGEST_RE.match(ev_stats["stream_sha256"])
    # Event workload intentionally reuses keys: ~size/20 canary chains.
    assert ev_stats["distinct_fact_count"] < 100_000

    key_stats = generator.stream_stats(101, 100_000, "distinct_fact_count")
    assert key_stats["distinct_fact_count"] == 100_000  # no catalogue exhaustion
    assert key_stats["event_count"] > 100_000          # revisions are separate
    assert key_stats["revision_count"] > 0
    assert key_stats["max_revision"] >= 2
    assert DIGEST_RE.match(key_stats["stream_sha256"])
    assert (ev_stats["stream_sha256"] != key_stats["stream_sha256"])


def test_m04_generator_repeatable_seed_hash_and_sizes():
    for size in (1_000, 10_000):
        first = generator.stream_stats(101, size, "event_count")
        second = generator.stream_stats(101, size, "event_count")
        assert first == second
        assert first["stream_sha256"] != generator.stream_stats(
            102, size, "event_count")["stream_sha256"]
    assert generator.stream_stats(50_000, 50_000, "distinct_fact_count")[
        "distinct_fact_count"] == 50_000
    small = generator.stream_stats(101, 100, "distinct_fact_count")
    assert small == generator.stream_stats(101, 100, "distinct_fact_count")
    assert small["distinct_fact_count"] == 100


def test_m04_qualified_keys_are_unique_and_qualified():
    seen = set()
    for i in range(500):
        key = generator.make_key(i, 101, manifest.load_protocol())
        canonical = key.canonical()
        assert canonical not in seen
        seen.add(canonical)
        assert len(canonical.split("|")) == 5
        assert key.token == f"T{i:08d}"


# ------------------------------------------------------------- EV-ORACLE
@pytest.mark.ev_oracle
def test_ev_oracle_matches_reviewed_miniature(miniature, reviewed_miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    assert reviewed_miniature["reviewed"] is True
    assert expected.to_json() == reviewed_miniature["expected"]
    assert expected.oracle_hash == reviewed_miniature["expected"]["oracle_hash"]

    decisions = expected.decisions
    assert decisions["ev-01"] == "applied"
    assert decisions["ev-02"] == "applied"
    assert decisions["ev-04"] == decisions["ev-05"] == "conflict"
    assert decisions["ev-07"] == "accepted_noncurrent"   # late
    assert decisions["ev-10"] == "accepted_pending"      # future
    assert expected.states == {
        "K/ALPHA": "current", "K/BETA": "absent", "K/CONFLICT": "conflict",
        "K/EPSILON": "future", "K/GAMMA": "withdrawn",
    }
    assert set(expected.current_set) == {"K/ALPHA"}
    assert expected.knowledge_seq == 9
    assert expected.cuts["K/ALPHA"] == 50

    table = oracle.review_table(miniature["events"], expected)
    assert [row["seq"] for row in table] == list(range(1, 11))
    assert {row["decision"] for row in table} >= {"conflict", "applied",
                                                  "accepted_noncurrent",
                                                  "accepted_pending"}


def test_ev_oracle_source_imports_no_product_module(repo_root):
    files = [os.path.join(repo_root, "tools", "ebrain", "v3-eval", f"{n}.py")
             for n in ("manifest", "generator", "oracle", "metrics", "runner",
                       "cli", "schema")]
    files.append(os.path.join(repo_root, "tools", "ebrain", "v3_eval",
                              "__init__.py"))
    for path in files:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        imported = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.append(node.module or "")
        assert not [name for name in imported
                    if name == "ebrain" or name.startswith("ebrain.")
                    or name.startswith("tools.ebrain.ebrain")], path


# -------------------------------------------------------------- EV-LABELS
def test_ev_labels_hidden_oracle_ids_absent_from_inputs(tmp_path, miniature,
                                                        fixture_dir, repo_root):
    out = str(tmp_path / "ds")
    sealed = generator.write_dataset(out, 101, 200, "event_count")
    assert manifest.verify_manifest(sealed)
    with open(os.path.join(out, "events.jsonl"), encoding="utf-8") as fh:
        text = fh.read()
    events = [json.loads(line) for line in text.splitlines() if line]
    labels = oracle.hidden_labels_for(events)
    assert len(labels) > 0
    assert not any(label in text for label in labels)
    assert not any(label in json.dumps(sealed) for label in labels)

    adapter_case = {"events": events, "scope": "s1", "as_of": 10_000}
    assert not any(label in json.dumps(adapter_case) for label in labels)
    with open(os.path.join(fixture_dir, "miniature_history.json"),
              encoding="utf-8") as fh:
        mini_text = fh.read()
    mini_labels = oracle.hidden_labels_for(miniature["events"])
    assert not any(label in mini_text for label in mini_labels)

    with open(os.path.join(fixture_dir, "negative_controls.py"),
              encoding="utf-8") as fh:
        contender_source = fh.read()
    assert not any(label in contender_source for label in mini_labels)
    with open(os.path.join(repo_root, "tools", "ebrain", "v3-eval",
                           "generator.py"), encoding="utf-8") as fh:
        generator_source = fh.read()
    assert "hidden_label" not in generator_source


# -------------------------------------------------------------- EV-SEALED
def test_ev_sealed_commitment_and_tuning_retires_suite(tmp_path):
    payload = {"suite_id": "sealed-independent-001", "salt": "owner-held",
               "seeds": [901], "manifest_schema_version": 1}
    digest = manifest.commitment(payload)
    assert DIGEST_RE.match(digest)
    assert manifest.verify_commitment(payload, digest)
    assert not manifest.verify_commitment({**payload, "seeds": [902]}, digest)

    state = manifest.new_suite_state(payload["suite_id"], digest)
    assert manifest.check_suite(state, payload, digest) == "OK"
    assert manifest.check_suite(state, payload, "0" * 64) == \
        "COMMITMENT_MISMATCH"
    assert manifest.check_suite({"suite_id": "x"}, payload, digest) == \
        "NOT_CONFIGURED"
    retired = manifest.retire_suite(state, "tuned on sealed failure")
    assert manifest.check_suite(retired, payload, digest) == "RETIRED"

    out = str(tmp_path / "ds-sealed")
    sealed = generator.write_dataset(out, 101, 50, "distinct_fact_count")
    assert manifest.verify_manifest(sealed)
    tampered = dict(sealed)
    tampered["counts"] = {**sealed["counts"], "event_count": 9999}
    assert not manifest.verify_manifest(tampered)


# --------------------------------------------------------------- EV-DENOM
def test_ev_denominator_pending_partial_clipped_and_delivered_bytes(miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    base = metrics.correct_answer(expected, query_id="q-mini")

    contender_decisions = dict(expected.decisions)
    contender_decisions["ev-08"] = "accepted_pending"  # was applied -> miss
    contender_decisions.pop("ev-01")                   # unassigned -> miss
    rows = {r.metric: r for r in metrics.filing_metrics(
        expected.decisions, contender_decisions)}
    assert rows["precision"].n == len(contender_decisions) == 9
    assert rows["recall"].n == len(expected.decisions) == 10
    # ev-10 is pending in the reviewed oracle plus the changed ev-08.
    assert rows["pending_count"].value == 2
    assert rows["unassigned_count"].value == 1
    assert rows["recall"].value < 1.0

    partial = metrics.correct_answer(expected, query_id="q-mini")
    partial.answer_status = "partial"
    facet = next(iter(expected.current_set.values())).facets
    dropped_key = sorted(facet)[0]
    partial.current["K/ALPHA"]["facets"].pop(dropped_key)
    partial.delivered_facets = sorted(k for k in facet if k != dropped_key)
    partial.delivered_bytes = metrics.delivered_size(partial)
    assert metrics.joint_exact(partial, expected) is False
    delivered = metrics.delivered_after_clipping(partial, expected, 10_000)
    assert delivered[0].value == 1                 # bytes reported == actual
    assert delivered[1].value == 0                 # clipped answer fails gate
    assert dropped_key in delivered[1].note

    assert metrics.rate("S", "empty", []).value == metrics.UNMEASURED
    assert metrics.rate("S", "empty", []).n == 0
    empty_rows = {r.metric: r for r in metrics.filing_metrics({}, {})}
    assert empty_rows["precision"].value == metrics.UNMEASURED


# -------------------------------------------------------------- EV-RUNTIME
def test_ev_runtime_digests_and_no_cached_substitution(fixture_dir, repo_root):
    ref = os.path.join(fixture_dir, "reference_contender.py")
    prod = os.path.join(fixture_dir, "product_contender.py")
    digests = {d["path"]: d["sha256"] for d in
               runner.harness_module_digests([ref, prod])}
    ref_rel = os.path.relpath(ref, repo_root).replace(os.sep, "/")
    prod_rel = os.path.relpath(prod, repo_root).replace(os.sep, "/")
    assert digests[ref_rel] != digests[prod_rel]
    assert DIGEST_RE.match(digests[ref_rel])

    # Legacy tests may already have imported product modules in a combined
    # pytest run, so assert that THIS harness adds none rather than that no
    # product module exists at all.
    before_product = {n for n in sys.modules
                      if n == "ebrain" or n.startswith("ebrain.")}
    mod_ref, rec_ref = runner.load_adapter(ref)
    mod_prod, rec_prod = runner.load_adapter(prod)
    assert rec_ref["module_name"] != rec_prod["module_name"]
    assert rec_ref["sha256"] != rec_prod["sha256"]
    assert mod_ref.Adapter.name != mod_prod.Adapter.name

    fresh_ref, fresh_rec = runner.load_adapter(ref)
    assert fresh_ref is not mod_ref           # no cached module substitution
    assert fresh_rec["sha256"] == rec_ref["sha256"]
    after_product = {n for n in sys.modules
                     if n == "ebrain" or n.startswith("ebrain.")}
    assert after_product == before_product

    command = runner.build_subprocess_command(ref, 101, 100, "event_count")
    assert command[1:4] == ["-m", "tools.ebrain.v3_eval.cli", "_worker"]
    assert "digests" in runner.RUNTIME_DESIGN


# ------------------------------------------------------- deterministic metrics
def test_metrics_all_seven_negative_controls_fail(miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    base = metrics.correct_answer(expected, query_id="q-mini")
    rows, results = metrics.evaluate_negative_controls(base, expected)
    assert [r.name for r in results] == manifest.load_protocol()["negative_controls"]
    assert all(r.correctly_failed for r in results)
    by_name = {r.name: r for r in results}
    assert by_name["true_plus_zombie"].detectors["zombie"]
    assert by_name["empty"].detectors["all_abstain"]
    assert by_name["always_current"].detectors["zombie"]
    assert by_name["dropped_facets"].gate["joint_exact"] is False
    assert by_name["wrong_sources"].gate["joint_exact"] is False
    assert by_name["wrong_scope"].gate["joint_exact"] is False
    assert by_name["label_leaking"].detectors["leak"]
    assert all(r.value == 1 for r in rows if r.metric.endswith("_fails"))


def test_metrics_denominators_per_seed_and_scenario(miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    good = metrics.correct_answer(expected, query_id="q1")
    bad = metrics.make_control("empty", good, expected)
    rows = metrics.compute_all([
        ("sequential", 101, good, expected),
        ("sequential", 102, bad, expected),
        ("conflict", 101, bad, expected),
    ])
    look = {(r.scenario, r.metric): r for r in rows}
    assert look[("101", "joint_exact")].n == 2
    assert look[("101", "joint_exact")].value == 0.5
    assert look[("102", "joint_exact")].n == 1
    assert look[("102", "joint_exact")].value == 0.0
    assert look[("conflict", "joint_exact")].n == 1
    assert look[("ALL", "joint_exact")].n == 3
    assert look[("ALL", "zombie_rate")].value == 0.0


def test_metrics_filing_retrieval_conflict_asof_ambiguity(miniature):
    expected = oracle.evaluate(miniature["events"],
                               scope=miniature["query"]["scope"],
                               as_of=miniature["query"]["as_of"])
    good = metrics.correct_answer(expected, query_id="q1")
    assert metrics.joint_exact(good, expected) is True
    assert metrics.zombie_detected(good, expected) is False
    assert metrics.label_leak(good, expected) is False

    retrieval = {r.arm if hasattr(r, "arm") else r.scenario: r.value
                 for r in metrics.retrieval_metrics({
                     "exact_before_rerank": (["a"], ["a", "b"]),
                     "exact_after_rerank": (["a", "b"], ["a", "b"]),
                     "empty_arm": ([], []),
                 })}
    assert retrieval["exact_before_rerank"] == 0.5
    assert retrieval["exact_after_rerank"] == 1.0
    assert retrieval["empty_arm"] == metrics.UNMEASURED

    assert metrics.conflict_accuracy([(good, expected)]).value == 1.0
    assert metrics.asof_accuracy([(good, expected)]).value == 1.0
    amb = {r.metric: r.value for r in metrics.ambiguity_metrics([
        (good, expected, True), (metrics.make_control("empty", good, expected),
                                 expected, False),
    ])}
    assert amb["ambiguous_recall"] == 1.0
    assert amb["answerable_abstention"] == 0.0
    assert amb["unanswerable_correct_abstention"] == 1.0


def test_runner_subprocess_records_sealed_evidence(fixture_dir):
    adapter = os.path.join(fixture_dir, "reference_contender.py")
    result = runner.run_contender_subprocess(adapter, 101, 100, "event_count")
    assert manifest.verify_manifest(result["manifest"])
    assert result["exit_code"] == 0
    assert result["payload"]["status"] == "OK"
    assert result["manifest"]["status"] == "OK"
    assert result["manifest"]["adapter"]["sha256"] == \
        result["payload"]["adapter"]["sha256"]
    assert "status=OK" in result["results_text"]
    assert runner._RESULT_PREFIX not in result["results_text"]


# -------------------------------------------------------------------- CLI
def test_cli_subcommands_and_exit_codes(capsys, tmp_path, fixture_dir):
    with pytest.raises(SystemExit) as exc:
        cli.main(["--help"])
    assert exc.value.code == 0
    assert "--help" in capsys.readouterr().out

    assert cli.main(["protocol"]) == 0
    assert "protocol_sha256=" in capsys.readouterr().out

    assert cli.main(["generate", "--seed", "101", "--size", "100",
                     "--mode", "distinct_fact_count", "--stream"]) == 0
    generated = json.loads(capsys.readouterr().out)
    assert generated["counts"]["distinct_fact_count"] == 100

    assert cli.main(["negative-controls"]) == 0
    assert "negative_controls=OK" in capsys.readouterr().out

    missing = os.path.join(fixture_dir, "does-not-exist.py")
    assert cli.main(["evaluate", "--adapter", missing]) == 3
    assert "NOT_RUN" in capsys.readouterr().out

    out = str(tmp_path / "ds")
    assert cli.main(["generate", "--seed", "101", "--size", "20",
                     "--mode", "event_count", "--out", out]) == 0
    capsys.readouterr()
    mpath = os.path.join(out, "dataset_manifest.json")
    assert cli.main(["verify-manifest", "--manifest", mpath]) == 0
    assert "manifest=OK" in capsys.readouterr().out

    doc = json.load(open(mpath, encoding="utf-8"))
    doc["counts"] = {"tampered": True}
    bad_path = str(tmp_path / "bad-manifest.json")
    _write_json(bad_path, doc)
    assert cli.main(["verify-manifest", "--manifest", bad_path]) == 6
    assert "manifest=TAMPERED" in capsys.readouterr().out


def test_H05_negative_controls(miniature):
    """Traceability alias: true+zombie and all-abstain both fail the joint gate."""
    test_h05_true_plus_zombie_and_all_empty_both_fail(miniature)
    test_metrics_all_seven_negative_controls_fail(miniature)
