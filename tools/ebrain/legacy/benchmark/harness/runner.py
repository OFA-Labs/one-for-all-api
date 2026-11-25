"""Benchmark runner: one contender, one dataset, rows appended to a CSV.

    python -m harness.runner --contender control --size 1000 --seed 101 \
        --out results.csv [--timeout-s 900]
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import shutil
import tempfile
import time
import traceback
from datetime import datetime, timezone

from . import HARNESS_VERSION
from .api import Query, Trace, Write
from .generate import World as GenWorld, generate
from .loader import code_hash, load_adapter_class
from .metrics import (UNMEASURED, MetricRow, QueryRecord, World, compute,
                      pct, statusmap)
from .truth import find_codes

COLUMNS = ["run_id", "contender", "code_hash", "harness_version", "size",
           "seed", "scenario", "metric", "value", "n", "unit", "note"]
MAINTAIN_EVERY = 250


class Timeout(Exception):
    pass


class Run:
    def __init__(self, contender: str, size: int, seed: int,
                 timeout_s: float) -> None:
        self.dir = os.path.abspath(contender)
        self.cls = load_adapter_class(self.dir)
        self.hash = code_hash(self.dir)
        self.name = getattr(self.cls, "name", None) or os.path.basename(
            self.dir.rstrip("/\\"))
        self.size, self.seed = size, seed
        self.ds = generate(size, seed)
        self.truth = self.ds.truth()
        self.world = World()
        self.records: list[QueryRecord] = []
        self.crashes = 0
        self.crash_notes: list[str] = []
        self.write_ms: list[float] = []
        self.maintain_ms: list[float] = []
        self.timeout_s = timeout_s
        self.deadline = 0.0
        self.extra: list[MetricRow] = []
        self.tmp = tempfile.mkdtemp(prefix="ebrain-")

    # ------------------------------------------------------------ utils
    def call(self, fn, *args):
        """Call an adapter method; count exceptions as crashes."""
        t0 = time.perf_counter_ns()
        try:
            out = fn(*args)
            err = None
        except Exception as e:  # noqa: BLE001 - contender code
            out, err = None, f"{type(e).__name__}: {e}"
            self.crashes += 1
            if len(self.crash_notes) < 5:
                self.crash_notes.append(err[:200])
        return out, (time.perf_counter_ns() - t0) / 1e6, err

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            raise Timeout()

    def query(self, ad, spec, phase: str = "stream") -> QueryRecord:
        b, ms, err = self.call(ad.query, spec.query)
        rec = QueryRecord(spec, b, ms, err, phase)
        self.records.append(rec)
        return rec

    def maintain(self, ad, now: int) -> None:
        _, ms, err = self.call(ad.maintain, now)
        if err is None:
            self.maintain_ms.append(ms)

    # ------------------------------------------------------------- main
    def run(self) -> list[MetricRow]:
        t_start = time.monotonic()
        self.deadline = t_start + self.timeout_s
        status = "ok"
        try:
            self._stream()
        except Timeout:
            status = "timeout"
        except Exception:  # harness bug or fatal adapter failure
            status = "fatal: " + traceback.format_exc(limit=3)[-300:]
        runtime = time.monotonic() - t_start
        shutil.rmtree(self.tmp, ignore_errors=True)
        if status != "ok":
            reason = "UNMEASURED (timeout)" if status == "timeout" else status
            return [MetricRow("ALL", "run_status", UNMEASURED, 0, "",
                              reason),
                    MetricRow("ALL", "runtime_s", round(runtime, 2), 1, "s")]
        rows = compute(self.records, self.truth, self.world, self.size)
        rows += self.extra
        rows.append(MetricRow("ALL", "write_p95_ms",
                              round(pct(self.write_ms, 95), 3)
                              if self.write_ms else UNMEASURED,
                              len(self.write_ms), "ms"))
        rows.append(MetricRow("ALL", "maintain_p95_ms",
                              round(pct(self.maintain_ms, 95), 3)
                              if self.maintain_ms else UNMEASURED,
                              len(self.maintain_ms), "ms"))
        rows.append(MetricRow("ALL", "crashes", self.crashes, 1, "count",
                              " | ".join(self.crash_notes)))
        rows.append(MetricRow("ALL", "runtime_s", round(runtime, 2), 1, "s"))
        return rows

    def _stream(self) -> None:
        ds = self.ds
        wd = os.path.join(self.tmp, "main")
        os.makedirs(wd)
        ad, _, err = self.call(self.cls, wd, {"seed": self.seed})
        if ad is None:
            raise RuntimeError(f"adapter init failed: {err}")
        n_writes, rejected_valid = 0, 0
        mal: dict[str, list[str]] = {}
        rb_maps: dict[str, dict[str, dict]] = {}
        rb_specs: dict[str, list] = {}
        for ev in ds.events:
            self.check_time()
            if ev.kind == "write":
                ack, ms, err = self.call(ad.write, ev.payload)
                self.write_ms.append(ms)
                if ack is not None and getattr(ack, "accepted", False):
                    self.world.add(ev.payload)
                else:
                    rejected_valid += 1
                n_writes += 1
                if n_writes % MAINTAIN_EVERY == 0:
                    self.maintain(ad, ev.ts)
            elif ev.kind == "malformed":
                w, mtype = ev.payload
                ack, _, err = self.call(ad.write, w)
                out = ("crash" if err else
                       "accepted" if getattr(ack, "accepted", False)
                       else "rejected")
                mal.setdefault(mtype, []).append(out)
            elif ev.kind == "query":
                self.query(ad, ev.payload)
            elif ev.kind == "session":
                self._session(ad, ev.payload)
            else:
                tag, specs = ev.payload
                rb_specs[tag] = specs
                rb_maps[tag] = {s.query.query_id: statusmap(
                    self.query(ad, s, "rb_record").bundle) for s in specs}
        self.maintain(ad, ds.final_ts)
        for spec in ds.heal_final:
            self.check_time()
            self.query(ad, spec, "final")
        # malformed + rejected rows
        outs = [o for v in mal.values() for o in v]
        self.extra.append(MetricRow(
            "ALL", "rejected_malformed_rate",
            round(outs.count("rejected") / len(outs), 4) if outs
            else UNMEASURED, len(outs), "share",
            "; ".join(f"{k}: {v.count('rejected')}/{len(v)} rejected, "
                      f"{v.count('crash')} crash" for k, v in sorted(
                          mal.items()))))
        self.extra.append(MetricRow("ALL", "rejected_valid_writes",
                                    rejected_valid, n_writes, "count"))
        ad = self._durability(ad, wd)
        self._rollback(ad, rb_specs, rb_maps)
        self.call(ad.close)
        self._two_instances()

    def _session(self, ad, s) -> None:
        rec = self.query(ad, s.spec, "session")
        if rec.bundle is None:
            return
        shown, mem, new = [], [], []
        for it in rec.bundle.items:
            shown.append(it.item_id)
            codes = find_codes(it.text)
            if s.memory_code in codes:
                mem.append(it.item_id)
            if s.new_code and s.new_code in codes:
                new.append(it.item_id)
        q = s.spec.query
        if s.hkind == "H1":
            followed, ignored = tuple(new), tuple(mem)
            note = (f"Session outcome: {s.new_path} says {s.new_code}; the "
                    f"remembered value {s.memory_code} was outdated, so I "
                    f"used the file.")
        elif s.hkind == "H2":
            followed, ignored, note = (), tuple(mem), ""
        else:
            followed, ignored = tuple(mem), ()
            note = f"Used {s.memory_code} as remembered; task succeeded."
        tr = Trace(s.session_id, q.ts, q.agent_id, q.project_id,
                   tuple(shown), followed, ignored, note)
        self.call(ad.observe, tr)

    # ------------------------------------------------- durability (S5)
    def _presence(self, ad, writes: list[Write], ts: int) -> set[str]:
        found = set()
        for i, w in enumerate(writes):
            self.check_time()
            q = Query(f"dur-{i}", ts, w.agent_id, w.project_id,
                      w.text[:1500], 1024, as_of=w.ts)
            b, _, _ = self.call(ad.query, q)
            if b is None:
                continue
            codes = {c for it in b.items for c in find_codes(it.text)}
            if set(find_codes(w.text)) & codes:
                found.add(w.op_id)
        return found

    def _durability(self, ad, wd: str):
        rng = random.Random(self.seed * 7919)
        coded = sorted((w for w in self.world.writes.values()
                        if find_codes(w.text) and not w.deleted),
                       key=lambda w: w.op_id)
        sample = rng.sample(coded, min(100, len(coded)))
        ts = self.ds.final_ts
        before = self._presence(ad, sample, ts)
        self.call(ad.close)
        ad2, _, err = self.call(self.cls, wd, {"seed": self.seed})
        self.extra.append(MetricRow("S5", "store_reopen_ok",
                                    0 if ad2 is None else 1, 1, "bool",
                                    err or ""))
        if ad2 is None:
            raise RuntimeError("reopen failed")
        after = self._presence(ad2, sample, ts)
        self.extra.append(MetricRow(
            "S5", "acked_lost_reopen", len(before - after), len(before),
            "writes", f"probes found before close: {len(before)}/"
            f"{len(sample)}"))
        self._lost = len(before - after)
        return ad2

    # ---------------------------------------------- S2 two instances
    def _two_instances(self) -> None:
        """Two Adapter instances on one workdir, alternating writes.

        Replaces the two-OS-process test (dropped from scope): an ack from
        either instance must be visible to a fresh third instance.
        """
        gw = GenWorld(self.seed + 991)
        ops = []
        for i in range(120):
            code = gw.code()
            ops.append(Write(
                op_id=gw.op_id(), ts=self.ds.final_ts + 1 + i // 2,
                agent_id=("claude", "codex")[i % 2], project_id="one-for-all",
                visibility="shared", kind="claim",
                text=f"Probe note {gw.hexid('n')}: queue shard "
                     f"{gw.rng.randint(1, 999)} owner is "
                     f"{gw.rng.choice(('ana', 'bo', 'cy', 'dee'))} ({code})."))
        base_wd = os.path.join(self.tmp, "two-base")
        wd = os.path.join(self.tmp, "two")
        os.makedirs(base_wd)
        os.makedirs(wd)
        base, _, _ = self.call(self.cls, base_wd, {"seed": self.seed})
        a, _, _ = self.call(self.cls, wd, {"seed": self.seed})
        b, _, _ = self.call(self.cls, wd, {"seed": self.seed})
        if base is None or a is None or b is None:
            self.extra.append(MetricRow("S2", "acked_lost_concurrent",
                                        UNMEASURED, 0, "writes",
                                        "adapter init failed"))
            return
        acked, errors = set(), 0
        for i, w in enumerate(ops):
            self.call(base.write, w)
            ack, _, err = self.call((a, b)[i % 2].write, w)
            if ack is not None and getattr(ack, "accepted", False):
                acked.add(w.op_id)
            else:
                errors += 1
        ts = ops[-1].ts
        found_base = self._presence(base, ops, ts)
        self.call(a.close)
        self.call(b.close)
        self.call(base.close)
        c, _, _ = self.call(self.cls, wd, {"seed": self.seed})
        found = self._presence(c, ops, ts) if c is not None else set()
        if c is not None:
            self.call(c.close)
        lost = len((acked & found_base) - found)
        self.extra.append(MetricRow(
            "S2", "acked_lost_concurrent", lost, len(acked & found_base),
            "writes", f"two instances alternating; {errors} writes not "
            f"acked; baseline retrieves {len(found_base)}/{len(ops)}"))
        self.extra.append(MetricRow("ALL", "acked_lost", self._lost + lost,
                                    1, "writes", "reopen + two-instance"))

    # ------------------------------------------------- rollback (S11)
    def _rollback(self, ad, specs: dict, maps: dict) -> None:
        pts = self.ds.rollback_points

        def check(tag: str, metric: str, note: str) -> None:
            self.call(ad.rollback, pts[tag])
            same = 0
            for s in specs[tag]:
                rec = self.query(ad, s, "rb_replay")
                same += statusmap(rec.bundle) == maps[tag][s.query.query_id]
            n = len(specs[tag])
            self.extra.append(MetricRow("S11", metric, int(same == n), n,
                                        "bool", f"{same}/{n} probes equal; "
                                        + note))
        check("rb1", "rollback_exact", "periodic maintain() ran after t_r")
        self.maintain(ad, self.ds.final_ts)
        check("rb2", "rollback_exact_maintain",
              "rollback after an extra maintain() on the rolled-back store")


def append_csv(path: str, run: Run, rows: list[MetricRow]) -> None:
    new = not os.path.exists(path)
    run_id = (f"{run.name}-{run.size}-{run.seed}-"
              f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    with open(path, "a", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        if new:
            wr.writerow(COLUMNS)
        for r in rows:
            wr.writerow([run_id, run.name, run.hash[:16], HARNESS_VERSION,
                         run.size, run.seed, r.scenario, r.metric, r.value,
                         r.n, r.unit, r.note])


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="E-Brain benchmark runner")
    ap.add_argument("--contender", required=True)
    ap.add_argument("--size", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=101)
    ap.add_argument("--out", default="results.csv")
    ap.add_argument("--timeout-s", type=float, default=900)
    a = ap.parse_args(argv)
    run = Run(a.contender, a.size, a.seed, a.timeout_s)
    rows = run.run()
    append_csv(a.out, run, rows)
    print(f"{run.name} size={a.size} seed={a.seed} hash={run.hash[:12]}")
    for r in rows:
        if r.scenario == "ALL" or r.metric.startswith(("acked", "rollback")):
            print(f"  {r.scenario:4} {r.metric:28} {r.value!s:>10}  n={r.n}"
                  f"  {r.note[:60]}")


if __name__ == "__main__":
    main()
