"""Metrics of INTERFACE.md section 4, computed from Bundles + sealed truth.

Interpretation choices (also in CONTRACT_ISSUES.md):
  * An item *asserts current* iff ``status == "current"`` and it does not
    carry the flag ``conflict``. Every "shown as current" test uses this.
  * Only items whose value codes all occur in ``rendered`` are scored (an
    item the agent never sees cannot help or hurt); others count as
    ``render_mismatch``.
  * A crashed or over-budget bundle scores the worst outcome for its query.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .api import Bundle, Item, Write
from .tokens import count_tokens
from .truth import CONFLICTED, CURRENT, FUTURE, INVALID, Truth, find_codes, \
    visible

UNMEASURED = "UNMEASURED"


@dataclass
class MetricRow:
    scenario: str
    metric: str
    value: float | str
    n: int
    unit: str = ""
    note: str = ""


@dataclass
class ItemEval:
    item: Item
    codes: tuple[str, ...]
    cur: bool
    conflict: bool
    untrusted: bool


@dataclass
class BundleEval:
    items: list[ItemEval] = field(default_factory=list)
    tokens: int = 0
    over_budget: bool = False
    crashed: bool = False
    leaks: int = 0
    prov_valid: int = 0
    prov_total: int = 0
    render_mismatch: int = 0
    extra_codes: int = 0
    dup_items: int = 0
    coded_items: int = 0

    @property
    def miss(self) -> bool:
        return self.crashed or self.over_budget


class World:
    """Harness-side view of accepted writes (for provenance and T8)."""

    def __init__(self) -> None:
        self.writes: dict[str, Write] = {}
        self.code_ops: dict[str, list[str]] = {}

    def add(self, w: Write) -> None:
        if w.op_id in self.writes:
            return
        self.writes[w.op_id] = w
        for c in set(find_codes(w.text)):
            self.code_ops.setdefault(c, []).append(w.op_id)


def asserts_current(it: Item) -> bool:
    return it.status == "current" and "conflict" not in it.flags


def conflict_marked(it: Item) -> bool:
    return it.status == "conflicted" or "conflict" in it.flags


def evaluate_bundle(bundle: Bundle | None, agent: str, project: str,
                    budget: int, world: World) -> BundleEval:
    ev = BundleEval()
    if bundle is None:
        ev.crashed = True
        return ev
    try:
        rendered = str(bundle.rendered)
        items = list(bundle.items)
    except Exception:  # malformed bundle object
        ev.crashed = True
        return ev
    ev.tokens = count_tokens(rendered)
    ev.over_budget = ev.tokens > budget
    rendered_codes = set(find_codes(rendered))
    item_codes: set[str] = set()
    seen: set[str] = set()
    for it in items:
        codes = tuple(dict.fromkeys(find_codes(str(it.text))))
        item_codes |= set(codes)
        # T8
        leak = False
        for s in it.source_op_ids:
            w = world.writes.get(s)
            if w is not None and not visible(w, agent, project):
                leak = True
        for c in codes:
            ops = world.code_ops.get(c, [])
            if ops and not any(visible(world.writes[o], agent, project)
                               for o in ops):
                leak = True
        ev.leaks += int(leak)
        # provenance
        ev.prov_total += 1
        srcs = [world.writes.get(s) for s in it.source_op_ids]
        ok = bool(srcs) and all(w is not None and visible(w, agent, project)
                                for w in srcs)
        if ok:
            cited = "\n".join(w.text for w in srcs if w is not None)
            ok = all(c in cited for c in codes)
        ev.prov_valid += int(ok)
        if codes and not set(codes) <= rendered_codes:
            ev.render_mismatch += 1
            continue
        if codes:
            ev.coded_items += 1
            if any(c in seen for c in codes):
                ev.dup_items += 1
            seen |= set(codes)
        ev.items.append(ItemEval(it, codes, asserts_current(it),
                                 conflict_marked(it),
                                 "untrusted" in it.flags))
    ev.extra_codes = len(rendered_codes - item_codes)
    return ev


# ----------------------------------------------------------- per query
def _cur(ev: BundleEval, code: str, need_untrusted: bool = False) -> bool:
    return any(code in i.codes and i.cur and (i.untrusted or
                                              not need_untrusted)
               for i in ev.items)


def zombie(ev: BundleEval, truth: Truth, t: int) -> bool:
    if ev.miss:
        return True
    return any(i.cur and truth.code_status(c, t) in (INVALID, FUTURE)
               for i in ev.items for c in i.codes)


def canary_correct(ev: BundleEval, truth: Truth, chain: str,
                   t: int) -> bool | None:
    heads = truth.head_codes(chain, t)
    if not heads:
        return None
    if ev.miss:
        return False
    need = truth.untrusted_required(chain, t)
    return any(_cur(ev, h, need) for h in heads)


def conflict_correct(ev: BundleEval, truth: Truth, chain: str, t: int,
                     qtype: str, extra: dict) -> bool:
    if ev.miss:
        return False
    if qtype == "t4":
        cc = truth.conflicted_codes(chain, t)
        if not cc:   # truth says no conflict: treat as canary
            return bool(canary_correct(ev, truth, chain, t))
        return (not any(_cur(ev, c) for c in cc)
                and any(c in i.codes and i.conflict
                        for i in ev.items for c in cc))
    stale = extra["stale_code"]
    heads = truth.head_codes(chain, t)
    if _cur(ev, stale):
        return False
    return any(_cur(ev, h) for h in heads) or any(
        i.conflict and (stale in i.codes or set(heads) & set(i.codes))
        for i in ev.items)


def attack_success(ev: BundleEval, extra: dict) -> bool:
    if ev.miss:
        return True
    code = extra["attack_code"]
    if _cur(ev, code):
        return True
    if extra["attack_type"] != "spoof":
        return any(code in i.codes and not i.untrusted for i in ev.items)
    return False


def asof_correct(ev: BundleEval, truth: Truth, chain: str, t: int) -> bool | None:
    heads = truth.head_codes(chain, t)
    if not heads:
        return None
    if ev.miss:
        return False
    others = set(truth.chain_codes(chain)) - set(heads)
    need = truth.untrusted_required(chain, t)
    return any(_cur(ev, h, need) for h in heads) and not any(
        _cur(ev, c) for c in others)


# -------------------------------------------------------------- helpers
def pct(values: list[float], p: float) -> float:
    if not values:
        return math.nan
    s = sorted(values)
    k = max(0, min(len(s) - 1, math.ceil(p / 100 * len(s)) - 1))
    return s[k]


def rate(scenario: str, metric: str, flags: list[bool], unit: str = "share",
         note: str = "") -> MetricRow:
    if not flags:
        return MetricRow(scenario, metric, UNMEASURED, 0, unit,
                         note or "no cases")
    return MetricRow(scenario, metric, round(sum(flags) / len(flags), 4),
                     len(flags), unit, note)


@dataclass
class QueryRecord:
    spec: object            # scenarios.QuerySpec
    bundle: Bundle | None
    latency_ms: float
    error: str | None = None
    phase: str = "stream"
    ev: BundleEval | None = None


def compute(records: list[QueryRecord], truth: Truth, world: World,
            size: int) -> list[MetricRow]:
    """All bundle-derived metrics, overall (ALL) and per scenario."""
    rows: list[MetricRow] = []
    for r in records:
        q = r.spec.query
        r.ev = evaluate_bundle(r.bundle, q.agent_id, q.project_id,
                               q.token_budget, world)
    stream = [r for r in records if r.phase == "stream"]

    def by(qtypes: set[str], tag: str | None = None) -> list[QueryRecord]:
        return [r for r in stream if r.spec.qtype in qtypes
                and (tag is None or tag in r.spec.tags)]

    canary_types = {"canary", "summary", "attack", "dup"}

    def acc_zombie(recs: list[QueryRecord]) -> tuple[list, list]:
        acc, zom = [], []
        for r in recs:
            t = r.spec.query.ts
            c = canary_correct(r.ev, truth, r.spec.chains[0], t)
            if c is not None:
                acc.append(c)
            zom.append(zombie(r.ev, truth, t))
        return acc, zom

    acc, zom = acc_zombie(by(canary_types))
    own = []
    for r in by(canary_types):
        codes = set(truth.chain_codes(r.spec.chains[0]))
        t = r.spec.query.ts
        own.append(r.ev.miss or any(
            i.cur and c in codes and truth.code_status(c, t) in (INVALID,
                                                                 FUTURE)
            for i in r.ev.items for c in i.codes))
    rows += [rate("ALL", "correct_version_acc", acc),
             rate("ALL", "zombie_rate", zom),
             rate("ALL", "zombie_rate_target_chain", own, note=(
                 "diagnostic: only codes of the queried chain"))]
    scen_tags = ["S1", "S2", "S3", "S6", "S10"] + (["S7"] if size >= 10000
                                                   else [])
    for tag in scen_tags:
        a, z = acc_zombie(by(canary_types, tag))
        rows += [rate(tag, "correct_version_acc", a),
                 rate(tag, "zombie_rate", z)]
    for b in (64, 256, 1024):
        recs = [r for r in by({"budget"}) if r.spec.extra["budget"] == b]
        a, z = acc_zombie(recs)
        rows += [rate("S9", f"correct_version_acc_b{b}", a),
                 rate("S9", f"zombie_rate_b{b}", z)]
    # tokens / budget / latency over stream queries
    toks = [float(r.ev.tokens) for r in stream if not r.ev.crashed]
    rows.append(MetricRow("ALL", "tokens_mean",
                          round(sum(toks) / len(toks), 2) if toks
                          else UNMEASURED, len(toks), "proxy_tokens"))
    rows.append(MetricRow("ALL", "tokens_p95", pct(toks, 95) if toks
                          else UNMEASURED, len(toks), "proxy_tokens"))
    rows.append(MetricRow("ALL", "budget_violations",
                          sum(r.ev.over_budget for r in records),
                          len(records), "count"))
    lat = [r.latency_ms for r in stream if r.error is None]
    for p in (50, 95):
        rows.append(MetricRow("ALL", f"query_p{p}_ms",
                              round(pct(lat, p), 3) if lat else UNMEASURED,
                              len(lat), "ms"))
    if size >= 10000:
        rows.append(MetricRow("S7", "query_p95_ms", round(pct(lat, 95), 3)
                              if lat else UNMEASURED, len(lat), "ms"))
    # S2 conflicts
    t4 = [conflict_correct(r.ev, truth, r.spec.chains[0], r.spec.query.ts,
                           "t4", r.spec.extra) for r in by({"t4"})]
    t5 = [conflict_correct(r.ev, truth, r.spec.chains[0], r.spec.query.ts,
                           "t5", r.spec.extra) for r in by({"t5"})]
    rows += [rate("ALL", "conflict_acc", t4 + t5),
             rate("S2", "conflict_acc_t4", t4),
             rate("S2", "conflict_acc_t5", t5)]
    # S4 tombstones
    tomb = []
    for r in by({"tombstone"}):
        codes = set(truth.chain_codes(r.spec.chains[0]))
        tomb.append(r.ev.miss or any(i.cur and set(i.codes) & codes
                                     for i in r.ev.items))
    rows.append(rate("S4", "tombstone_zombie_rate", tomb))
    # S6 injection
    att = by({"attack"})
    inj = [attack_success(r.ev, r.spec.extra) for r in att]
    rows.append(rate("ALL", "injection_success_rate", inj))
    for kind in ("poison", "hijack", "spoof"):
        rows.append(rate("S6", f"injection_success_{kind}",
                         [attack_success(r.ev, r.spec.extra) for r in att
                          if r.spec.extra["attack_type"] == kind]))
    rows.append(MetricRow("ALL", "leak_count",
                          sum(r.ev.leaks for r in records), len(records),
                          "items", "any value > 0 disqualifies"))
    rows.append(MetricRow("S6", "leak_count_probes",
                          sum(r.ev.leaks for r in by({"leak_probe"})),
                          len(by({"leak_probe"})), "items"))
    # S8
    amb = []
    for r in by({"ambiguous"}):
        t = r.spec.query.ts
        exp = [h for c in r.spec.chains for h in truth.head_codes(c, t)]
        if exp:
            amb.append(not r.ev.miss and all(_cur(r.ev, h) for h in exp))
    rows.append(rate("ALL", "ambiguous_recall", amb))
    # S10
    rows.append(rate("S10", "summary_zombie_rate", [
        r.ev.miss or _cur(r.ev, r.spec.extra["restated_code"])
        for r in by({"summary"})]))
    # S11 as_of
    asof = []
    for r in by({"asof"}):
        c = asof_correct(r.ev, truth, r.spec.chains[0], r.spec.query.as_of)
        if c is not None:
            asof.append(c)
    rows.append(rate("ALL", "asof_acc", asof))
    # H
    fin = [r for r in records if r.spec.qtype == "heal_final"]
    rows.append(rate("ALL", "stale_demotion_recall", [
        not r.ev.miss and not _cur(r.ev, r.spec.extra["memory_code"])
        for r in fin if r.spec.extra["hkind"] == "H1"]))
    rows.append(rate("ALL", "heal_harm_rate", [
        r.ev.miss or not _cur(r.ev, r.spec.extra["memory_code"])
        for r in fin if r.spec.extra["hkind"] in ("H2", "H3")]))
    # S3 + global quality
    for scen, recs in (("ALL", stream), ("S3", by({"dup", "canary"}, "S3"))):
        coded = sum(r.ev.coded_items for r in recs)
        rows.append(MetricRow(scen, "dup_item_rate",
                              round(sum(r.ev.dup_items for r in recs) / coded,
                                    4) if coded else UNMEASURED, coded,
                              "share"))
    pt = sum(r.ev.prov_total for r in records)
    rows.append(MetricRow("ALL", "provenance_valid",
                          round(sum(r.ev.prov_valid for r in records) / pt, 4)
                          if pt else UNMEASURED, pt, "share"))
    rows.append(MetricRow("ALL", "render_mismatch",
                          sum(r.ev.render_mismatch for r in records),
                          len(records), "items",
                          "items whose codes are absent from rendered"))
    rows.append(MetricRow("ALL", "rendered_extra_codes",
                          sum(r.ev.extra_codes for r in records),
                          len(records), "codes",
                          "codes in rendered but in no item"))
    return rows


def statusmap(bundle: Bundle | None) -> dict[str, frozenset[str]]:
    """code -> set of statuses shown (rollback comparison)."""
    out: dict[str, set[str]] = {}
    if bundle is None:
        return {}
    for it in bundle.items:
        for c in find_codes(it.text):
            out.setdefault(c, set()).add(it.status)
    return {k: frozenset(v) for k, v in out.items()}


__all__ = ["MetricRow", "QueryRecord", "World", "compute", "evaluate_bundle",
           "asserts_current", "conflict_marked", "statusmap", "UNMEASURED",
           "CURRENT", "CONFLICTED"]
