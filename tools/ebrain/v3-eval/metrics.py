"""V3 scoring: joint exact, detection metrics and negative controls.

JOINT EXACT is the primary gate: the returned current set must equal the
oracle's authorized current set, with matching state, provenance and every
requested facet actually delivered. Legacy presence is reported *alongside*
it and can never compensate for a joint-exact failure (H05).

Empty and zero-denominator results are ``UNMEASURED`` / ``NOT_RUN``, never a
measured pass. All functions are deterministic and import no product code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from . import manifest
from .oracle import Expected, hidden_label

UNMEASURED = "UNMEASURED"


@dataclass
class MetricRow:
    scenario: str
    metric: str
    value: float | int | str
    n: int
    unit: str = "share"
    note: str = ""


@dataclass
class Answer:
    """Sanitized contender answer after delivery/clipping."""

    query_id: str
    scenario: str
    current: dict[str, dict[str, Any]] = field(default_factory=dict)
    answer_status: str = "complete"
    abstained: bool = False
    delivered_facets: list[str] = field(default_factory=list)
    rendered: str = ""
    delivered_bytes: int | None = None
    leaked_labels: tuple[str, ...] = ()

    def to_json(self) -> dict[str, Any]:
        return {
            "query_id": self.query_id,
            "scenario": self.scenario,
            "current": self.current,
            "answer_status": self.answer_status,
            "abstained": self.abstained,
            "delivered_facets": list(self.delivered_facets),
            "rendered": self.rendered,
            "delivered_bytes": self.delivered_bytes,
            "leaked_labels": list(self.leaked_labels),
        }


def rate(scenario: str, metric: str, flags: list[bool], unit: str = "share",
         note: str = "") -> MetricRow:
    if not flags:
        return MetricRow(scenario, metric, UNMEASURED, 0, unit,
                         note or "zero denominator: NOT_RUN")
    return MetricRow(scenario, metric, round(sum(flags) / len(flags), 4),
                     len(flags), unit, note)


def correct_answer(expected: Expected, query_id: str = "q",
                   scenario: str = "sequential") -> Answer:
    """Build the fully delivered, joint-exact answer for an oracle view."""
    current = {
        key: {
            "value": fv.value,
            "state": fv.state,
            "provenance": list(fv.provenance),
            "facets": dict(fv.facets),
        }
        for key, fv in expected.current_set.items()
    }
    facets = sorted({k for fv in expected.current_set.values()
                     for k in fv.facets})
    rendered = " ".join(str(fv.value) for fv in expected.current_set.values()
                        if fv.value is not None)
    ans = Answer(
        query_id=query_id, scenario=scenario, current=current,
        answer_status="complete", abstained=not expected.current_set,
        delivered_facets=facets, rendered=rendered,
    )
    ans.delivered_bytes = delivered_size(ans)
    return ans


def delivered_size(answer: Answer) -> int:
    """Bytes of the canonical delivered payload (used for byte accounting)."""
    return len(manifest.canonical_json({
        "current": answer.current,
        "answer_status": answer.answer_status,
        "delivered_facets": answer.delivered_facets,
        "rendered": answer.rendered,
    }))


def missing_facets(answer: Answer, expected: Expected) -> set[str]:
    needed = {k for fv in expected.current_set.values() for k in fv.facets}
    if not answer.delivered_facets:
        return set()  # empty list means "full structured answer declared"
    return needed - set(answer.delivered_facets)


def joint_exact(answer: Answer, expected: Expected) -> bool:
    """Primary gate: authorized set + state + provenance + delivered facets."""
    if missing_facets(answer, expected):
        return False
    if expected.current_set:
        if answer.answer_status != "complete" or answer.abstained:
            return False
        if set(answer.current) != set(expected.current_set):
            return False
        for key, want in expected.current_set.items():
            got = answer.current[key]
            if got.get("value") != want.value:
                return False
            if got.get("state") != "current" or want.state != "current":
                return False
            if set(got.get("provenance") or ()) != set(want.provenance):
                return False
            for facet, value in want.facets.items():
                if got.get("facets", {}).get(facet) != value:
                    return False
        return True
    # Unanswerable cut: correct only with a clean, labelled abstention.
    return answer.abstained and not answer.current


def legacy_presence(answer: Answer, expected: Expected) -> MetricRow:
    """Diagnostic only: does the value appear in delivered text at all?"""
    n = len(expected.current_set)
    if not n:
        return MetricRow("ALL", "legacy_presence", UNMEASURED, 0,
                         note="zero denominator: NOT_RUN")
    hits = sum(1 for fv in expected.current_set.values()
               if fv.value is not None and str(fv.value) in answer.rendered)
    return MetricRow("ALL", "legacy_presence", round(hits / n, 4), n)


def zombie_detected(answer: Answer, expected: Expected) -> bool:
    """Any non-authorized or non-current fact asserted as current."""
    for key, got in answer.current.items():
        if got.get("state") != "current":
            continue
        if key not in expected.current_set:
            return True
        if expected.states.get(key) != "current":
            return True
        # A superseded/wrong value asserted as current is also a zombie,
        # even when the qualified key itself is the right one.
        if got.get("value") != expected.current_set[key].value:
            return True
    return False


def all_abstain(answer: Answer) -> bool:
    return bool(answer.abstained) and not answer.current


def always_current(answer: Answer, expected: Expected) -> bool:
    return all(answer.current.get(k, {}).get("state") == "current"
               for k in expected.all_keys) and bool(answer.current)


def label_leak(answer: Answer, expected: Expected) -> bool:
    labels = {fv.hidden for fv in expected.current_set.values()}
    labels.update(hidden_label(k) for k in expected.all_keys)
    return (bool(answer.leaked_labels)
            or any(label in answer.rendered for label in labels))


def gate(answer: Answer, expected: Expected) -> dict[str, Any]:
    """Single contender decision. No average can waive a failed determinism."""
    je = joint_exact(answer, expected)
    zom = zombie_detected(answer, expected)
    leak = label_leak(answer, expected)
    return {
        "joint_exact": je,
        "legacy_presence": legacy_presence(answer, expected).value,
        "zombie": zom,
        "label_leak": leak,
        "all_abstain": all_abstain(answer),
        "gate_pass": je and not zom and not leak,
    }


# ----------------------------------------------------------- negative controls
@dataclass
class ControlResult:
    name: str
    gate: dict[str, Any]
    correctly_failed: bool
    detectors: dict[str, bool]


def make_control(name: str, base: Answer, expected: Expected) -> Answer:
    """Derive a deliberately broken contender answer from a correct one."""
    a = Answer(**{k: v for k, v in base.to_json().items()})
    a.current = {k: dict(v) for k, v in base.current.items()}
    a.current = {k: {**v, "facets": dict(v.get("facets") or {}),
                     "provenance": list(v.get("provenance") or [])}
                 for k, v in a.current.items()}
    extras = [k for k in expected.all_keys if k not in expected.current_set]
    if name == "true_plus_zombie":
        key = extras[0] if extras else "K/ZOMBIE"
        a.current[key] = {"value": "STALE", "state": "current",
                          "provenance": ["op-stale"],
                          "facets": dict(expected.all_facts[key].facets)
                          if key in expected.all_facts else {}}
        a.rendered += " STALE"
    elif name == "empty":
        a.current, a.abstained, a.rendered = {}, True, ""
        a.delivered_facets = []
    elif name == "always_current":
        for key in expected.all_keys:
            a.current.setdefault(key, {"value": "CURRENT", "state": "current",
                                       "provenance": ["op-any"], "facets": {}})
    elif name == "dropped_facets":
        for fact in a.current.values():
            if fact["facets"]:
                fact["facets"].pop(next(iter(fact["facets"])))
        a.delivered_facets = sorted({k for f in a.current.values()
                                     for k in f["facets"]})
    elif name == "wrong_sources":
        for fact in a.current.values():
            fact["provenance"] = ["op-not-a-source"]
    elif name == "wrong_scope":
        for fact in a.current.values():
            fact["facets"]["scope"] = "s-other"
        if "scope" not in a.delivered_facets:
            a.delivered_facets.append("scope")
    elif name == "label_leaking":
        label = hidden_label(next(iter(expected.current_set))) \
            if expected.current_set else hidden_label("K/NONE")
        a.leaked_labels = (label,)
        a.rendered += " " + label
    else:
        raise ValueError(f"unknown negative control {name!r}")
    a.delivered_bytes = delivered_size(a)
    return a


def evaluate_negative_controls(
    base: Answer, expected: Expected, names: Iterable[str] | None = None,
) -> tuple[list[MetricRow], list[ControlResult]]:
    """Every listed control MUST fail the gate; otherwise the suite is broken."""
    control_names = list(names) if names is not None else [
        "true_plus_zombie", "empty", "always_current", "dropped_facets",
        "wrong_sources", "wrong_scope", "label_leaking",
    ]
    rows: list[MetricRow] = []
    results: list[ControlResult] = []
    for name in control_names:
        answer = make_control(name, base, expected)
        g = gate(answer, expected)
        detectors = {
            "zombie": g["zombie"],
            "all_abstain": g["all_abstain"],
            "joint_exact_false": not g["joint_exact"],
            "leak": g["label_leak"],
        }
        correctly_failed = not g["gate_pass"]
        results.append(ControlResult(name, g, correctly_failed, detectors))
        rows.append(MetricRow("NEG", f"{name}_fails",
                              int(correctly_failed), 1, "bool",
                              "control must be rejected"))
        rows.append(MetricRow("NEG", f"{name}_joint_exact",
                              int(g["joint_exact"]), 1, "bool"))
    return rows, results


# ------------------------------------------------------------------ denominators
def filing_metrics(expected_decisions: dict[str, str],
                   contender_decisions: dict[str, str]) -> list[MetricRow]:
    """Filing precision/recall; pending and unassigned decisions are misses."""
    exp_applied = {op for op, d in expected_decisions.items()
                   if d == "applied"}
    got_applied = {op for op, d in contender_decisions.items()
                   if d == "applied"}
    tp = exp_applied & got_applied
    precision = round(len(tp) / len(contender_decisions), 4) \
        if contender_decisions else UNMEASURED
    recall = round(len(tp) / len(expected_decisions), 4) \
        if expected_decisions else UNMEASURED
    pending = sum(1 for d in contender_decisions.values()
                  if d == "accepted_pending")
    unassigned = sum(1 for op in expected_decisions
                     if op not in contender_decisions)
    return [
        MetricRow("FILING", "precision", precision, len(contender_decisions),
                  note="pending counts as a miss"),
        MetricRow("FILING", "recall", recall, len(expected_decisions),
                  note="pending/unassigned count as misses"),
        MetricRow("FILING", "pending_count", pending, len(contender_decisions),
                  "count"),
        MetricRow("FILING", "unassigned_count", unassigned,
                  len(expected_decisions), "count"),
    ]


def retrieval_metrics(arms: dict[str, tuple[list[str], list[str]]]
                      ) -> list[MetricRow]:
    """Per-arm / pre-post-rerank recall with explicit denominators."""
    rows = []
    for arm, (retrieved, expected) in sorted(arms.items()):
        if not expected:
            rows.append(MetricRow(arm, "retrieval_recall", UNMEASURED, 0,
                                  note="zero denominator: NOT_RUN"))
            continue
        hits = len(set(retrieved) & set(expected))
        rows.append(MetricRow(arm, "retrieval_recall",
                              round(hits / len(expected), 4), len(expected)))
    return rows


def conflict_accuracy(cases: list[tuple[Answer, Expected]]) -> MetricRow:
    """Conflict cases must not assert a conflicted fact as current."""
    flags = []
    for answer, expected in cases:
        conflicted = {k for k, s in expected.states.items()
                      if s == "conflict"}
        if conflicted:
            flags.append(all(k not in answer.current for k in conflicted))
        else:
            flags.append(joint_exact(answer, expected))
    return rate("CONFLICT", "conflict_accuracy", flags)


def asof_accuracy(cases: list[tuple[Answer, Expected]]) -> MetricRow:
    flags = []
    for answer, expected in cases:
        future = {k for k, s in expected.states.items() if s == "future"}
        flags.append(joint_exact(answer, expected)
                     and all(k not in answer.current for k in future))
    return rate("ASOF", "asof_accuracy", flags)


def ambiguity_metrics(
    cases: list[tuple[Answer, Expected, bool]],
) -> list[MetricRow]:
    answerable = [(a, e) for a, e, is_ans in cases if is_ans]
    unanswerable = [(a, e) for a, e, is_ans in cases if not is_ans]
    amb_flags = [
        bool(e.current_set) and all(
            fv.value is not None and str(fv.value) in a.rendered
            for fv in e.current_set.values())
        for a, e in answerable
    ]
    abst_flags = [a.abstained for a, _ in answerable]
    unans_flags = [a.abstained and not a.current for a, _ in unanswerable]
    return [
        rate("AMBIG", "ambiguous_recall", amb_flags),
        rate("AMBIG", "answerable_abstention", abst_flags),
        rate("AMBIG", "unanswerable_correct_abstention", unans_flags),
    ]


def delivered_after_clipping(answer: Answer, expected: Expected,
                             budget_bytes: int) -> list[MetricRow]:
    """Re-score the bytes actually delivered after compact clipping."""
    computed = delivered_size(answer)
    match = answer.delivered_bytes == computed
    dropped = missing_facets(answer, expected)
    within = computed <= budget_bytes
    return [
        MetricRow("DELIVERY", "delivered_bytes_match", int(match), 1, "bool",
                  f"reported={answer.delivered_bytes} actual={computed}"),
        MetricRow("DELIVERY", "delivered_after_clipping",
                  int(gate(answer, expected)["gate_pass"] and not dropped
                      and within),
                  max(1, len(expected.current_set)), "bool",
                  f"dropped_facets={sorted(dropped)} bytes={computed} "
                  f"budget={budget_bytes}"),
    ]


def compute_all(
    cases: list[tuple[str, int, Answer, Expected]],
) -> list[MetricRow]:
    """Aggregate joint/exlegacy/zombie with per-seed and per-scenario n."""
    rows: list[MetricRow] = []
    groups: dict[tuple[str, str | int], list[tuple[Answer, Expected]]] = {}
    for scenario, seed, answer, expected in cases:
        g = gate(answer, expected)
        groups.setdefault(("ALL", "ALL"), []).append((answer, expected))
        groups.setdefault(("SEED", seed), []).append((answer, expected))
        groups.setdefault(("SCENARIO", scenario), []).append((answer, expected))
    for (kind, key), items in sorted(groups.items(), key=lambda kv: str(kv[0])):
        flags = [gate(a, e)["joint_exact"] for a, e in items]
        zom = [gate(a, e)["zombie"] for a, e in items]
        rows.append(rate(str(key), "joint_exact", flags))
        rows.append(rate(str(key), "zombie_rate", zom))
    return rows


__all__ = [
    "UNMEASURED", "MetricRow", "Answer", "rate", "correct_answer",
    "delivered_size", "missing_facets", "joint_exact", "legacy_presence",
    "zombie_detected", "all_abstain", "always_current", "label_leak", "gate",
    "ControlResult", "make_control", "evaluate_negative_controls",
    "filing_metrics", "retrieval_metrics", "conflict_accuracy",
    "asof_accuracy", "ambiguity_metrics", "delivered_after_clipping",
    "compute_all",
]
