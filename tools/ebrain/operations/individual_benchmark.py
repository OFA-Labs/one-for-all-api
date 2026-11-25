"""Focused individual-developer benchmark (synthetic, in-process service).

Measures joint-exact accuracy, retrieval+resolver latency and delivered context
tokens for 1k/10k memories with 1/3/5 same-owner agent sessions. No enterprise
load claim is made; no model or network call is involved.
"""
from __future__ import annotations

import argparse
import datetime
import json
import statistics
import threading
import time
from pathlib import Path

from ebrain.v3.clocks import FakeClock
from ebrain.v3.config import V3Config
from ebrain.v3.contracts import Action, Grant, Principal, Selector
from ebrain.v3.service import V3Service

API = Path(__file__).resolve().parents[3]
OUT = API / "docs/ebrain/implementation-plan/evidence/individual-benchmark"
ORG = "org-demo"
SCOPE = "one-for-all"


def principal() -> Principal:
    return Principal(
        subject="owner", org_id=ORG,
        grants=(Grant(scope=SCOPE, predicates=("*",), actions=tuple(Action),
                      authority="human"),),
        auth_epoch=1,
    )


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * p))]


def run(size: int, sessions: int, queries: int) -> dict[str, object]:
    from ebrain.v3.auth.context import build_context
    from ebrain.v3.contracts import ClaimKind, WriteRequest
    from ebrain.v3.identity.keys import canonical_key

    from ebrain.v3.quotas.plans import PlanPolicy
    svc = V3Service.build(cfg=V3Config(), clock=FakeClock(),
                          plan=PlanPolicy("company_100k"))
    p = principal()
    ctx = build_context(p, request_id=f"bench-{sessions}", scope=SCOPE)
    expected: dict[str, str] = {}
    for n in range(size):
        # One stable resource per memory: size writes == size distinct qualified facts.
        resource = f"svc-{n}"
        env = ("dev", "stage", "prod")[n % 3]
        branch = ("main", "feature")[n % 2]
        value = f"value-{n}"
        key = canonical_key(
            org_id=ORG, scope=SCOPE, resource_namespace="repo",
            resource_id=resource, predicate="repo.branch.head.sha",
            kind=ClaimKind.ASSERTION,
            qualifiers={"repo": "one-for-all-api", "environment": env,
                        "branch": branch},
        )
        svc.write(ctx, WriteRequest(
            op_id=f"op-{n}", key=key, value=value, source_id="synthetic",
            source_revision=f"r{n}", idempotency_key=f"op-{n}",
            valid_from="2025-01-01T00:00:00+00:00",
        ))
        expected[key.canonical()] = value

    latencies: list[float] = []
    tokens: list[int] = []
    correct = 0
    lock = threading.Lock()

    def worker(worker_id: int) -> None:
        nonlocal correct
        picks = list(expected.items())[worker_id::sessions][:queries]
        for canonical, value in picks:
            selector = Selector(
                scope=SCOPE, predicate="repo.branch.head.sha",
                resource_id=canonical.split("|")[3],
                qualifiers=tuple(
                    pair.split("=", 1) for pair in canonical.split("|")[6].split("&") if pair
                ),
            )
            start = time.perf_counter()
            answer = svc.query(ctx, selector)
            elapsed = (time.perf_counter() - start) * 1000
            from ebrain.models import count_tokens
            delivered = answer.answer_status.value + "".join(
                str(i.current_value) for i in answer.items
            )
            # Joint exact: exactly one current item with the exact expected value.
            exact = (
                answer.answer_status.value == "complete"
                and len(answer.items) == 1
                and answer.items[0].state.value == "current"
                and answer.items[0].current_value == value
            )
            with lock:
                latencies.append(elapsed)
                tokens.append(count_tokens(delivered))
                if exact:
                    correct += 1

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(sessions)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    total = min(queries * sessions, len(expected))
    return {
        "memories": size,
        "distinct_qualified_facts": len(expected),
        "sessions": sessions,
        "queries_executed": len(latencies),
        "joint_exact_correct": correct,
        "joint_exact": round(correct / total, 4) if total else 0.0,
        "latency_ms_p50": round(statistics.median(latencies), 3),
        "latency_ms_p95": round(percentile(latencies, 0.95), 3),
        "latency_ms_p99": round(percentile(latencies, 0.99), 3),
        "context_tokens_median": statistics.median(tokens),
        "context_tokens_max": max(tokens),
    }


def main() -> int:
    parser = argparse.ArgumentParser(prog="individual-benchmark")
    parser.add_argument("--sizes", default="1000,10000")
    parser.add_argument("--queries", type=int, default=60)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "hardware": "AMD Ryzen AI 5 340, 6 physical/12 logical cores, Windows 11 build 26300",
        "workload": "80/20 read/write profile approximated by write-then-read; synthetic local service",
        "targets": {"joint_exact": 0.95, "p95_ms": 200, "recall": 0.99, "filing": 0.98},
        "runs": [],
    }
    for size in (int(v) for v in args.sizes.split(",")):
        for sessions in (1, 3, 5):
            result = run(size, sessions, args.queries)
            report["runs"].append(result)
            print(json.dumps(result, sort_keys=True))
    path = OUT / "benchmark.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("evidence", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
