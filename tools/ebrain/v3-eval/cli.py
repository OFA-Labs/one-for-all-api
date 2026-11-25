"""Command-line interface for the versioned V3 evaluation harness.

    python -m tools.ebrain.v3_eval.cli --help

Exit codes: 0 OK, 2 usage, 3 NOT_RUN, 4 threshold/gate FAIL,
5 negative-control broken, 6 manifest/commitment verification failed,
7 worker error. A missing adapter is always NOT_RUN, never a measured pass.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import generator, manifest, metrics, oracle, runner

EXIT_OK, EXIT_USAGE, EXIT_NOT_RUN = 0, 2, 3
EXIT_THRESHOLD, EXIT_NEGCTRL, EXIT_MANIFEST, EXIT_WORKER = 4, 5, 6, 7

FIXTURES = os.path.join(runner.SOURCE_DIR, "fixtures")


def _load_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _miniature() -> tuple[dict[str, Any], oracle.Expected, metrics.Answer]:
    doc = _load_json(os.path.join(FIXTURES, "miniature_history.json"))
    expected = oracle.evaluate(doc["events"], scope=doc["query"]["scope"],
                               as_of=doc["query"]["as_of"])
    answer = metrics.correct_answer(
        expected, query_id=doc["query"]["query_id"], scenario="miniature")
    return doc, expected, answer


def cmd_protocol(args: argparse.Namespace) -> int:
    proto = manifest.load_protocol()
    text = json.dumps(proto, indent=2, sort_keys=True)
    print(text)
    print(f"protocol_sha256={manifest.protocol_hash()}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return EXIT_OK


def cmd_generate(args: argparse.Namespace) -> int:
    if args.size < 0:
        print("ERROR: --size must be >= 0", file=sys.stderr)
        return EXIT_USAGE
    if args.stream:
        stats = generator.stream_stats(args.seed, args.size, args.mode)
        print(json.dumps({"seed": args.seed, "size": args.size,
                          "mode": args.mode, "counts": stats}, sort_keys=True))
        return EXIT_OK
    if args.out:
        sealed = generator.write_dataset(
            args.out, args.seed, args.size, args.mode)
        print(json.dumps({"out": args.out, "counts": sealed["counts"],
                          "manifest_sha256": sealed["manifest_sha256"]},
                         sort_keys=True))
        return EXIT_OK
    stats = generator.stream_stats(args.seed, args.size, args.mode)
    print(json.dumps({"seed": args.seed, "size": args.size,
                      "mode": args.mode, "counts": stats}, sort_keys=True))
    return EXIT_OK


def _write_evidence(evidence_dir: str | None, result: dict[str, Any]) -> None:
    if not evidence_dir:
        return
    run_dir = os.path.join(evidence_dir, result["manifest"]["run_id"])
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(result["manifest"], fh, indent=2, sort_keys=True)
    with open(os.path.join(run_dir, "results.txt"), "w",
              encoding="utf-8") as fh:
        fh.write(result["results_text"])


def cmd_evaluate(args: argparse.Namespace) -> int:
    proto = manifest.load_protocol()
    threshold = (args.threshold if args.threshold is not None
                 else float(proto["thresholds"]["joint_exact"]))
    result = runner.run_contender_subprocess(
        args.adapter, args.seed, args.size, args.mode,
        timeout_s=args.timeout_s, protocol=proto)
    _write_evidence(args.evidence_dir, result)
    payload = result["payload"]
    print(result["results_text"], end="")
    if payload.get("status") == "NOT_RUN":
        print(f"NOT_RUN: {payload.get('reason', 'adapter missing')} "
              "(no accuracy number is claimed)")
        return EXIT_NOT_RUN
    if payload.get("status") != "OK":
        print(f"FAIL: {payload.get('reason', 'worker failed')}")
        return EXIT_THRESHOLD
    gate = payload.get("gate", {})
    presence = gate.get("legacy_presence", metrics.UNMEASURED)
    je = 1.0 if gate.get("joint_exact") else 0.0
    zombie = float(gate.get("zombie", 1.0))
    ok = (je >= threshold and not gate.get("zombie")
          and not gate.get("label_leak")
          and (presence == metrics.UNMEASURED or float(presence) >= threshold)
          and zombie <= float(proto["thresholds"]["zombie_rate"]))
    print(f"threshold={threshold} joint_exact={je} "
          f"legacy_presence={presence} zombie={zombie} "
          f"decision={'PASS' if ok else 'FAIL'}")
    return EXIT_OK if ok else EXIT_THRESHOLD


def cmd_negative_controls(args: argparse.Namespace) -> int:
    _doc, expected, base = _miniature()
    rows, results = metrics.evaluate_negative_controls(base, expected)
    if args.json:
        print(json.dumps({"rows": [r.__dict__ for r in rows],
                          "controls": [{"name": r.name,
                                        "correctly_failed": r.correctly_failed,
                                        "detectors": r.detectors,
                                        "gate": r.gate}
                                       for r in results]}, sort_keys=True,
                         indent=2))
    else:
        for r in results:
            print(f"{r.name:18} correctly_failed={r.correctly_failed} "
                  f"detectors={r.detectors}")
    good = all(r.correctly_failed for r in results)
    print(f"negative_controls={'OK' if good else 'BROKEN'} "
          f"n={len(results)}")
    return EXIT_OK if good else EXIT_NEGCTRL


def cmd_verify_manifest(args: argparse.Namespace) -> int:
    if args.commitment is not None:
        if not args.payload:
            print("ERROR: --commitment requires --payload", file=sys.stderr)
            return EXIT_USAGE
        payload = _load_json(args.payload)
        ok = manifest.verify_commitment(payload, args.commitment)
        print(f"commitment={'OK' if ok else 'MISMATCH'} "
              f"expected={manifest.commitment(payload)}")
        return EXIT_OK if ok else EXIT_MANIFEST
    if not args.manifest:
        print("ERROR: provide --manifest or --commitment", file=sys.stderr)
        return EXIT_USAGE
    doc = _load_json(args.manifest)
    ok = manifest.verify_manifest(doc)
    print(f"manifest={'OK' if ok else 'TAMPERED'} "
          f"expected={manifest.manifest_hash(doc)} "
          f"found={doc.get('manifest_sha256')}")
    return EXIT_OK if ok else EXIT_MANIFEST


def cmd_worker(args: argparse.Namespace) -> int:
    payload = runner.run_one(args.adapter, args.seed, args.size, args.mode)
    print(runner._RESULT_PREFIX + json.dumps(payload, sort_keys=True))
    return EXIT_OK if payload.get("status") == "OK" else EXIT_WORKER


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="tools.ebrain.v3_eval.cli",
        description="Test-only V3 deterministic evaluation harness",
    )
    subs = ap.add_subparsers(dest="command", required=True)

    p = subs.add_parser("protocol", help="print the frozen protocol and hash")
    p.add_argument("--out", help="optional JSON output path")
    p.set_defaults(func=cmd_protocol)

    p = subs.add_parser("generate", help="generate or stream a dataset")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--mode", choices=manifest.load_protocol()["dataset"]["modes"],
                   required=True)
    p.add_argument("--out", help="directory for events.jsonl + manifest")
    p.add_argument("--stream", action="store_true",
                   help="count/hash without writing files")
    p.set_defaults(func=cmd_generate)

    p = subs.add_parser("evaluate", help="run one contender subprocess")
    p.add_argument("--adapter", default=None,
                   help="path to adapter module or directory")
    p.add_argument("--seed", type=int, default=101)
    p.add_argument("--size", type=int, default=1000)
    p.add_argument("--mode", default="event_count",
                   choices=manifest.load_protocol()["dataset"]["modes"])
    p.add_argument("--threshold", type=float, default=None,
                   help="minimum joint exact / legacy presence (default: protocol)")
    p.add_argument("--timeout-s", type=float, default=900.0)
    p.add_argument("--evidence-dir", default=None,
                   help="directory to receive <run-id>/manifest.json + results.txt")
    p.set_defaults(func=cmd_evaluate)

    p = subs.add_parser("negative-controls",
                        help="assert every intentionally broken contender fails")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_negative_controls)

    p = subs.add_parser("verify-manifest", help="verify a seal or commitment")
    p.add_argument("--manifest", help="sealed evidence/dataset manifest")
    p.add_argument("--commitment", help="sealed-suite commitment hash")
    p.add_argument("--payload", help="JSON payload for --commitment")
    p.set_defaults(func=cmd_verify_manifest)

    p = subs.add_parser("_worker", help=argparse.SUPPRESS)
    p.add_argument("--adapter", required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--mode", required=True)
    p.set_defaults(func=cmd_worker)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
