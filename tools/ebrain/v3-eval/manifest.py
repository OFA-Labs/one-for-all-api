"""Deterministic manifest building, hashing and sealed commitments.

Everything here is stdlib-only and test-owned. A manifest is always sealed
with a ``manifest_sha256`` over its canonical JSON (sorted keys, compact
separators). Verification recomputes that hash and refuses to trust an
unsealed or modified document.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Any

CANON: dict[str, Any] = {
    "sort_keys": True,
    "separators": (",", ":"),
    "ensure_ascii": True,
}

_HERE = os.path.dirname(os.path.abspath(__file__))
PROTOCOL_PATH = os.path.join(_HERE, "protocol.json")


def canonical_json(obj: Any) -> bytes:
    """Canonical UTF-8 JSON bytes (the only hashing representation)."""
    return json.dumps(obj, **CANON).encode("utf-8")


def sha256_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_data(text.encode("utf-8"))


def sha256_json(obj: Any) -> str:
    return sha256_data(canonical_json(obj))


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def load_protocol(path: str | None = None) -> dict[str, Any]:
    with open(path or PROTOCOL_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def protocol_hash(path: str | None = None) -> str:
    """Hash of the frozen protocol document itself."""
    return sha256_file(path or PROTOCOL_PATH)


def source_digests(paths: list[str], root: str | None = None) -> list[dict[str, str]]:
    """Stable, sorted list of ``{path, sha256}`` for supplied source files."""
    out: list[dict[str, str]] = []
    base = os.path.abspath(root) if root else None
    for p in paths:
        full = os.path.abspath(p)
        rel = os.path.relpath(full, base).replace(os.sep, "/") if base else p
        out.append({"path": rel, "sha256": sha256_file(full)})
    return sorted(out, key=lambda d: d["path"])


def git_state(root: str) -> dict[str, str]:
    """Record HEAD and a cheap deterministic dirty-content digest.

    The dirty digest is sha256 over the canonical ``git status --porcelain``
    output. It detects a changed working tree without reading or printing any
    file contents (and therefore cannot leak a secret).
    """
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
            text=True, check=False,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=root, capture_output=True,
            text=True, check=False,
        ).stdout
    except OSError:
        head, status = "NOT_A_GIT_REPO", ""
    return {
        "git_head": head or "UNKNOWN",
        "dirty_digest": sha256_text(status),
    }


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def run_id(digest_hint: str, when: str | None = None) -> str:
    """<UTC timestamp>-<hash8> as required by the evidence layout."""
    stamp = (when or utc_now()).replace(":", "").replace("-", "")
    return f"{stamp}-{sha256_text(digest_hint)[:8]}"


def manifest_hash(manifest: dict[str, Any]) -> str:
    """Hash a manifest, ignoring an existing seal so it is idempotent."""
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    return sha256_json(body)


def seal_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(manifest)
    sealed["manifest_sha256"] = manifest_hash(manifest)
    return sealed


def verify_manifest(manifest: dict[str, Any]) -> bool:
    seal = manifest.get("manifest_sha256")
    return isinstance(seal, str) and seal == manifest_hash(manifest)


def commitment(payload: Any) -> str:
    """Sealed-suite commitment. The payload stays with the independent owner."""
    return sha256_json(payload)


def verify_commitment(payload: Any, digest: str) -> bool:
    return commitment(payload) == digest


def new_suite_state(suite_id: str, digest: str) -> dict[str, Any]:
    """Initial state of an independent sealed suite (owned by the evaluator)."""
    return {"suite_id": suite_id, "status": "ACTIVE", "commitment": digest,
            "retired_reason": None}


def retire_suite(state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Tuning on a sealed failure permanently retires that suite."""
    retired = dict(state)
    retired["status"] = "RETIRED"
    retired["retired_reason"] = reason
    return retired


def check_suite(state: dict[str, Any], payload: Any,
                digest: str) -> str:
    """Return OK / NOT_CONFIGURED / COMMITMENT_MISMATCH / RETIRED.

    A retired suite cannot be re-activated by revealing or recommitting the
    same payload; a new independent suite is required.
    """
    if state.get("status") == "RETIRED":
        return "RETIRED"
    if state.get("status") != "ACTIVE" or not state.get("commitment"):
        return "NOT_CONFIGURED"
    if state.get("commitment") != digest or not verify_commitment(payload, digest):
        return "COMMITMENT_MISMATCH"
    return "OK"


def build_evidence_manifest(
    *,
    run_id_value: str,
    command: list[str],
    cwd: str,
    python_version: str,
    python_executable: str,
    seed: int | None = None,
    size: int | None = None,
    mode: str | None = None,
    protocol: dict[str, Any] | None = None,
    dataset_hash: str | None = None,
    oracle_hash: str | None = None,
    adapter: dict[str, Any] | None = None,
    counts: dict[str, int] | None = None,
    status: str = "NOT_RUN",
    exit_code: int | None = None,
    source_digest_list: list[dict[str, str]] | None = None,
    git: dict[str, str] | None = None,
    limitations: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble an unsealed evidence manifest; callers seal it explicitly."""
    proto = protocol or load_protocol()
    state = git or {}
    manifest: dict[str, Any] = {
        "manifest_schema_version": proto["manifest_schema_version"],
        "run_id": run_id_value,
        "created_at_utc": utc_now(),
        "command": list(command),
        "cwd": cwd,
        "python": {
            "version": python_version,
            "executable": python_executable,
        },
        "git_head": state.get("git_head", "UNKNOWN"),
        "dirty_digest": state.get("dirty_digest", "UNKNOWN"),
        "protocol_id": proto["protocol_id"],
        "protocol_version": proto["protocol_version"],
        "protocol_hash": protocol_hash(),
        "seed": seed,
        "size": size,
        "mode": mode,
        "dataset_hash": dataset_hash,
        "oracle_hash": oracle_hash,
        "adapter": adapter or {},
        "counts": counts or {},
        "status": status,
        "exit_code": exit_code,
        "source_digests": source_digest_list or [],
        "limitations": limitations or [],
        "failure_policy": proto["failure_policy"],
    }
    if extra:
        manifest["extra"] = extra
    return manifest


__all__ = [
    "CANON", "canonical_json", "sha256_data", "sha256_text", "sha256_json",
    "sha256_file", "load_protocol", "protocol_hash", "source_digests",
    "git_state", "utc_now", "run_id", "manifest_hash", "seal_manifest",
    "verify_manifest", "commitment", "verify_commitment", "new_suite_state",
    "retire_suite", "check_suite", "build_evidence_manifest",
]
