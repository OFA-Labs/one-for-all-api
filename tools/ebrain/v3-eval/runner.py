"""Clean-subprocess contender runner with sanitized evidence manifests.

An adapter is loaded under a unique module name on every call, so a cached
reference module can never be substituted for the requested contender. The
public CLI spawns a fresh interpreter per contender (the ``_worker`` hidden
subcommand); only whitelisted, non-secret fields are returned.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Any

from . import generator, manifest, metrics, oracle

SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SOURCE_DIR)))
HARNESS_MODULES = (
    "schema", "manifest", "generator", "oracle", "metrics", "runner", "cli",
)

RUNTIME_DESIGN = (
    "One contender per fresh OS subprocess; adapter imported under a unique "
    "module name and re-executed on every load (no sys.modules reuse); "
    "harness and adapter module digests + file paths recorded in the evidence "
    "manifest; environment variables matching secret patterns are removed; "
    "results are whitelisted and sanitized before writing."
)

_SECRET_KEY = re.compile(
    r"(SECRET|TOKEN|PASSWORD|PASSWD|CREDENTIAL|API_KEY|PRIVATE_KEY|_KEY$)",
    re.IGNORECASE,
)
_RESULT_PREFIX = "V3EVAL_RESULT:"


def sanitize_env() -> dict[str, str]:
    """Copy the environment, dropping secret-looking variable names."""
    return {k: v for k, v in os.environ.items() if not _SECRET_KEY.search(k)}


def harness_source_paths(extra: list[str] | None = None) -> list[str]:
    paths = [os.path.join(SOURCE_DIR, f"{name}.py")
             for name in HARNESS_MODULES]
    paths.append(os.path.join(SOURCE_DIR, "protocol.json"))
    if extra:
        paths.extend(os.path.abspath(p) for p in extra)
    return paths


def harness_module_digests(extra: list[str] | None = None
                           ) -> list[dict[str, str]]:
    return manifest.source_digests(harness_source_paths(extra), REPO_ROOT)


def load_adapter(path: str) -> tuple[Any, dict[str, str]]:
    """Load ``path/adapter.py`` or a single adapter module, freshly."""
    full = os.path.abspath(path)
    if os.path.isdir(full):
        full = os.path.join(full, "adapter.py")
    if not os.path.isfile(full):
        raise FileNotFoundError(f"adapter module not found: {full}")
    name = "v3_contender_" + manifest.sha256_text(full)[:12]
    sys.modules.pop(name, None)  # never reuse a cached module substitution
    spec = importlib.util.spec_from_file_location(name, full)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import adapter from {full}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        raise
    record = {
        "module_name": name,
        "file": os.path.relpath(full, REPO_ROOT).replace(os.sep, "/"),
        "sha256": manifest.sha256_file(full),
    }
    return module, record


def build_subprocess_command(adapter_path: str, seed: int, size: int,
                             mode: str) -> list[str]:
    # ``-m`` is invoked from REPO_ROOT by the caller, so the alias package is
    # importable without a hand-edited PYTHONPATH.
    return [
        sys.executable, "-m", "tools.ebrain.v3_eval.cli", "_worker",
        "--adapter", os.path.abspath(adapter_path),
        "--seed", str(seed), "--size", str(size), "--mode", mode,
    ]


def _construct(module: Any, config: dict[str, Any], workdir: str) -> Any:
    cls = getattr(module, "Adapter", None)
    if cls is None:
        return module
    try:
        return cls(config, workdir)
    except TypeError:
        return cls(config)


def _answer_from(data: dict[str, Any], scenario: str) -> metrics.Answer:
    """Whitelist adapter output fields; ignore any extra (untrusted) keys."""
    current = data.get("current") or {}
    if not isinstance(current, dict):
        current = {}
    return metrics.Answer(
        query_id=str(data.get("query_id", "q")),
        scenario=str(data.get("scenario", scenario)),
        current={str(k): dict(v) if isinstance(v, dict) else {}
                 for k, v in current.items()},
        answer_status=str(data.get("answer_status", "complete")),
        abstained=bool(data.get("abstained", False)),
        delivered_facets=[str(x) for x in (data.get("delivered_facets") or [])],
        rendered=str(data.get("rendered", "")),
        delivered_bytes=(int(data["delivered_bytes"])
                         if data.get("delivered_bytes") is not None else None),
        leaked_labels=tuple(str(x) for x in (data.get("leaked_labels") or [])),
    )


def run_one(adapter_path: str, seed: int, size: int, mode: str,
            protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run one contender on one (seed, size, mode) inside the current process."""
    proto = protocol or manifest.load_protocol()
    if not (os.path.isfile(adapter_path) or os.path.isdir(adapter_path)):
        return {"status": "NOT_RUN", "reason": "adapter missing",
                "adapter": {"file": adapter_path, "sha256": None}}
    module, adapter_record = load_adapter(adapter_path)
    events = list(generator.iter_events(seed, size, mode, proto))
    stats = generator.DatasetStats()
    for ev in events:
        stats.add(ev)
    counts = stats.finish()
    expected = oracle.evaluate(
        [ev.to_json() for ev in events], scope="s1",
        as_of=max((ev.ts for ev in events), default=0),
    )
    config = {"seed": seed, "size": size, "mode": mode, "scope": "s1",
              "query_id": "q-run"}
    with tempfile.TemporaryDirectory(prefix="v3eval-") as workdir:
        adapter = _construct(module, config, workdir)
        decisions: dict[str, str] = {}
        write_fn = getattr(adapter, "write", None)
        if callable(write_fn):
            for ev in events:
                try:
                    ack = write_fn(ev.to_json())
                except Exception as exc:  # contender failures are measured
                    decisions[ev.op_id] = f"EXCEPTION:{type(exc).__name__}"
                    continue
                status = (ack.get("status") if isinstance(ack, dict)
                          else getattr(ack, "status", None))
                decisions[ev.op_id] = str(status or "unknown")
        query_fn = getattr(adapter, "query", None)
        case = {
            "query_id": "q-run", "scope": "s1",
            "as_of": expected.as_of,
            "facets": sorted({k for fv in expected.current_set.values()
                              for k in fv.facets}),
            "events": [ev.to_json() for ev in events],
        }
        raw = query_fn(case) if callable(query_fn) else None
        close_fn = getattr(adapter, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                pass
    answer = _answer_from(raw if isinstance(raw, dict) else {}, "sequential")
    answer.delivered_bytes = metrics.delivered_size(answer)
    g = gate = metrics.gate(answer, expected)
    rows = metrics.compute_all([("sequential", seed, answer, expected)])
    rows += metrics.filing_metrics(expected.decisions, decisions)
    return {
        "status": "OK",
        "adapter": adapter_record,
        "harness_modules": harness_module_digests([adapter_record["file"]]),
        "dataset": counts,
        "dataset_hash": counts["stream_sha256"],
        "oracle_hash": expected.oracle_hash,
        "gate": {k: v for k, v in gate.items()},
        "rows": [r.__dict__ for r in rows],
        "answer": answer.to_json(),
        "runtime_design": RUNTIME_DESIGN,
    }


def sanitize_results(payload: dict[str, Any]) -> str:
    """Render only whitelisted, secret-free rows to a text report."""
    lines = [f"status={payload.get('status')}"]
    adapter = payload.get("adapter") or {}
    lines.append(f"adapter={adapter.get('file')} sha256={adapter.get('sha256')}")
    for row in payload.get("rows") or []:
        lines.append("{scenario:8} {metric:28} {value!s:>10} n={n}".format(**{
            k: row.get(k, "") for k in ("scenario", "metric", "value", "n")
        }))
    return "\n".join(lines) + "\n"


def run_contender_subprocess(
    adapter_path: str, seed: int, size: int, mode: str,
    *, timeout_s: float = 900.0, protocol: dict[str, Any] | None = None,
    test_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Spawn a clean interpreter for one contender; return sealed evidence."""
    proto = protocol or manifest.load_protocol()
    command = build_subprocess_command(adapter_path, seed, size, mode)
    exists = os.path.isfile(adapter_path) or os.path.isdir(adapter_path)
    if not exists:
        payload = {"status": "NOT_RUN", "reason": "adapter missing",
                   "adapter": {"file": adapter_path, "sha256": None},
                   "rows": []}
        exit_code = 3
        stdout, stderr = "", "NOT_RUN: adapter missing"
    else:
        try:
            proc = subprocess.run(
                command, cwd=REPO_ROOT, env=sanitize_env(),
                capture_output=True, text=True, timeout=timeout_s, check=False,
            )
        except subprocess.TimeoutExpired:
            payload = {"status": "FAIL", "reason": "timeout", "rows": []}
            exit_code, stdout, stderr = 4, "", "TIMEOUT"
        else:
            exit_code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
            payload = None
            for line in stdout.splitlines():
                if line.startswith(_RESULT_PREFIX):
                    try:
                        payload = json.loads(line[len(_RESULT_PREFIX):])
                    except json.JSONDecodeError:
                        payload = None
            if payload is None:
                payload = {"status": "FAIL", "reason": "worker no result",
                           "rows": [], "stderr": stderr[-500:]}
    body = manifest.build_evidence_manifest(
        run_id_value=manifest.run_id(
            f"{adapter_path}|{seed}|{size}|{mode}|{exit_code}"),
        command=command, cwd=REPO_ROOT,
        python_version=sys.version.split()[0],
        python_executable=sys.executable,
        seed=seed, size=size, mode=mode, protocol=proto,
        dataset_hash=(payload.get("dataset_hash")
                      if isinstance(payload, dict) else None),
        oracle_hash=(payload.get("oracle_hash")
                     if isinstance(payload, dict) else None),
        adapter=payload.get("adapter") if isinstance(payload, dict) else None,
        counts={**(payload.get("dataset", {}) if isinstance(payload, dict)
                   else {}), **(test_counts or {})},
        status=str(payload.get("status", "FAIL")),
        exit_code=exit_code,
        source_digest_list=harness_module_digests(),
        git=manifest.git_state(REPO_ROOT),
        limitations=["synthetic data only; no sealed or live-model evidence"],
        extra={"failure_policy": proto["failure_policy"],
               "runtime_design": RUNTIME_DESIGN,
               "worker_reason": payload.get("reason")
               if isinstance(payload, dict) else None},
    )
    sealed = manifest.seal_manifest(body)
    return {
        "payload": payload,
        "manifest": sealed,
        "results_text": sanitize_results(payload),
        "exit_code": exit_code,
        "command": command,
    }


__all__ = [
    "SOURCE_DIR", "REPO_ROOT", "HARNESS_MODULES", "RUNTIME_DESIGN",
    "sanitize_env", "harness_source_paths", "harness_module_digests",
    "load_adapter", "build_subprocess_command", "run_one", "sanitize_results",
    "run_contender_subprocess",
]
