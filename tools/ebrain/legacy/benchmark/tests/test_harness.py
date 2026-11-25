"""Harness self-tests: generator, truth rules T1-T8, metrics, contracts."""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from harness.api import AdapterProtocol, Bundle, Item, Query, Write  # noqa
from harness.generate import generate, stream_hash  # noqa: E402
from harness.loader import code_hash, load_adapter_class  # noqa: E402
from harness.metrics import (World, attack_success, canary_correct,  # noqa
                             conflict_correct, evaluate_bundle, zombie)
from harness.truth import (CONFLICTED, CURRENT, INVALID, ROLE_COPY,  # noqa
                           ROLE_TOMBSTONE, ROLE_VERSION, Seal, Truth, visible)


def W(op, ts, code="", agent="claude", **kw) -> Write:
    base = dict(op_id=op, ts=ts, agent_id=agent, project_id="p",
                visibility="shared", kind="claim",
                text=f"fact {code}".strip())
    base.update(kw)
    return Write(**base)


def truth(*specs):
    """specs: (Write, role, code, of)."""
    writes = [s[0] for s in specs]
    seals = {s[0].op_id: Seal("c", s[1], s[2], s[3] if len(s) > 3 else None)
             for s in specs}
    return Truth(writes, seals)


A, B, C = "VC-AAAAAA", "VC-BBBBBB", "VC-CCCCCC"


# ------------------------------------------------------------ generator
def test_generator_deterministic():
    assert stream_hash(generate(1000, 101)) == stream_hash(generate(1000, 101))
    assert stream_hash(generate(1000, 101)) != stream_hash(generate(1000, 102))
    ds = generate(1000, 101)
    assert len(ds.writes) == 1000
    for w in ds.writes:
        seal = ds.seals.get(w.op_id)
        if seal and seal.code:
            assert seal.code in w.text


# ---------------------------------------------------------------- truth
def test_t1_recency():
    t = truth((W("a", 1, A), ROLE_VERSION, A), (W("b", 2, B), ROLE_VERSION, B))
    assert t.head_codes("c", 1) == [A]
    assert t.head_codes("c", 2) == [B]
    assert t.code_status(A, 2) == INVALID


def test_t2_authority():
    t = truth((W("a", 1, A, authority="human"), ROLE_VERSION, A),
              (W("b", 2, B), ROLE_VERSION, B),
              (W("c", 3, C, supersedes=("a",)), ROLE_VERSION, C))
    assert t.head_codes("c", 2) == [A]          # silent agent loses
    assert t.head_codes("c", 3) == [C]          # explicit supersedes wins


def test_t3_provenance():
    t = truth((W("a", 1, A), ROLE_VERSION, A),
              (W("b", 2, B, provenance="external", supersedes=("a",)),
               ROLE_VERSION, B))
    assert t.head_codes("c", 2) == [A]
    t2 = truth((W("a", 1, A, provenance="external"), ROLE_VERSION, A))
    assert t2.head_codes("c", 1) == [A] and t2.untrusted_required("c", 1)


def test_t4_concurrency():
    t = truth((W("a", 1, A), ROLE_VERSION, A),
              (W("b", 2, B, agent="claude"), ROLE_VERSION, B),
              (W("x", 2, C, agent="codex"), ROLE_VERSION, C),
              (W("d", 3, "VC-DDDDDD"), ROLE_VERSION, "VC-DDDDDD"))
    assert t.head_codes("c", 2) == []
    assert t.conflicted_codes("c", 2) == sorted([B, C])
    assert t.code_status(B, 2) == CONFLICTED
    assert t.head_codes("c", 3) == ["VC-DDDDDD"]


def test_t5_stale_base():
    t = truth((W("a", 1, A), ROLE_VERSION, A),
              (W("b", 2, B, supersedes=("a",)), ROLE_VERSION, B),
              (W("c", 3, C, agent="codex", supersedes=("a",)),
               ROLE_VERSION, C))
    assert t.head_codes("c", 3) == [B]
    assert t.code_status(C, 3) == INVALID


def test_t6_tombstone_and_dangling():
    t = truth((W("a", 1, A, kind="spec", path="d.md",
                 supersedes=("op-never",)), ROLE_VERSION, A),
              (W("t", 2, "", kind="spec", path="d.md", deleted=True,
                 text="Deleted d.md"), ROLE_TOMBSTONE, None))
    assert t.head_codes("c", 1) == [A]
    assert t.head_codes("c", 2) == [] and t.code_status(A, 2) == INVALID


def test_t7_summary_copy():
    t = truth((W("a", 1, A), ROLE_VERSION, A), (W("b", 2, B), ROLE_VERSION, B),
              (W("s", 3, A, kind="summary"), ROLE_COPY, A, "a"))
    assert t.head_codes("c", 3) == [B]
    assert t.code_status(A, 3) == INVALID


def test_t8_isolation():
    w = W("a", 1, A, visibility="private", agent="codex")
    assert visible(w, "codex", "p")
    assert not visible(w, "claude", "p")
    assert not visible(W("b", 1, A), "claude", "other")


# -------------------------------------------------------------- metrics
def _world(*ws):
    wd = World()
    for w in ws:
        wd.add(w)
    return wd


def _ev(items, world, budget=500, agent="claude"):
    rendered = "\n".join(f"[{i.status}] {i.text}" for i in items)
    return evaluate_bundle(Bundle(tuple(items), rendered), agent, "p",
                           budget, world)


def test_metrics_zombie_conflict_untrusted_leak_budget():
    a, b = W("a", 1, A), W("b", 2, B)
    t = truth((a, ROLE_VERSION, A), (b, ROLE_VERSION, B))
    wd = _world(a, b)
    ev = _ev([Item("1", a.text, "current", ("a",)),
              Item("2", b.text, "current", ("b",))], wd)
    assert zombie(ev, t, 2) and canary_correct(ev, t, "c", 2)
    ev = _ev([Item("2", b.text, "current", ("b",))], wd)
    assert not zombie(ev, t, 2)
    # conflicted pair scores correct
    x, y = W("x", 3, A, agent="codex"), W("y", 3, C, agent="voice")
    tc = truth((W("a0", 1, "VC-000000"), ROLE_VERSION, "VC-000000"),
               (x, ROLE_VERSION, A), (y, ROLE_VERSION, C))
    wd2 = _world(x, y)
    ev = _ev([Item("1", x.text, "conflicted", ("x",), ("conflict",)),
              Item("2", y.text, "conflicted", ("y",), ("conflict",))], wd2)
    assert conflict_correct(ev, tc, "c", 3, "t4", {})
    ev = _ev([Item("1", x.text, "current", ("x",))], wd2)
    assert not conflict_correct(ev, tc, "c", 3, "t4", {})
    # untrusted flag handling
    e = W("e", 1, A, provenance="external")
    ev = _ev([Item("1", e.text, "unknown", ("e",))], _world(e))
    assert attack_success(ev, {"attack_code": A, "attack_type": "poison"})
    ev = _ev([Item("1", e.text, "quarantined", ("e",), ("untrusted",))],
             _world(e))
    assert not attack_success(ev, {"attack_code": A,
                                   "attack_type": "poison"})
    # leak detection
    p = W("p", 1, A, visibility="private", agent="codex")
    ev = _ev([Item("1", p.text, "current", ("p",))], _world(p))
    assert ev.leaks == 1
    # budget violation is a miss
    ev = _ev([Item("2", b.text * 50, "current", ("b",))], wd, budget=5)
    assert ev.over_budget and not canary_correct(ev, t, "c", 2)


# -------------------------------------------------------------- contracts
@pytest.mark.parametrize("name", ["control", "naive"])
def test_contract(name, tmp_path):
    cls = load_adapter_class(os.path.join(ROOT, name))
    assert len(code_hash(os.path.join(ROOT, name))) == 64
    wd = str(tmp_path / "wd")
    ad = cls(wd, {"seed": 1})
    assert isinstance(ad, AdapterProtocol)
    w = Write("op-1", 1, "claude", "p", "shared", "claim",
              f"The auth token TTL is 45 minutes ({A}).")
    assert ad.write(w).accepted
    assert ad.write(w).accepted                       # idempotent
    assert not ad.write(Write("op-1", 1, "claude", "p", "shared", "claim",
                              "different")).accepted
    assert not ad.write(Write("op-2", 1, "claude", "p", "shared", "claim",
                              "")).accepted
    assert not ad.write(Write("op-3", 1, "claude", "p", "shared", "memo",
                              "x")).accepted           # type: ignore
    assert not ad.write(Write("op-4", 1, "claude", "p", "shared", "claim",
                              "x" * 20001)).accepted
    ad.close()
    ad = cls(wd, {"seed": 1})                          # durability
    b = ad.query(Query("q", 2, "claude", "p", "auth token TTL", 256))
    assert any(A in i.text for i in b.items)
    ad.close()
