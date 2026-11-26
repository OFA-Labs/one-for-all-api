"""Deterministic, rehearsal-only legacy -> V3 export and reconciliation.

Never reads production data unless an explicit path is supplied. Never writes
to the source SQLite file. Fuzzy chain ids are candidates only; mixed or
ambiguous chains are quarantined, never force-merged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ebrain.v3.contracts import digest_of


def _read_only_uri(path: Path) -> str:
    return f"file:{path.as_posix()}?mode=ro"


@dataclass(frozen=True)
class ExportManifest:
    source_path: str
    source_sha256: str
    high_water_seq: int
    tables: dict[str, int]
    rows_digest: str
    quarantined: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "high_water_seq": self.high_water_seq,
            "tables": self.tables,
            "rows_digest": self.rows_digest,
            "quarantined": list(self.quarantined),
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def export(source: Path, destination: Path) -> ExportManifest:
    """Immutable sanitized export of a legacy SQLite store (read-only connection)."""
    if not source.exists():
        raise FileNotFoundError(source)
    conn = sqlite3.connect(_read_only_uri(source), uri=True)
    conn.row_factory = sqlite3.Row
    try:
        tables = {
            name: int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
            for name in ("ops", "codes", "terms", "traces", "heal", "links")
            if conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
        }
        rows = conn.execute(
            "SELECT seq, user_id, op_id, ts, project, kind, path, auth, ext, sup, deleted, digest "
            "FROM ops ORDER BY seq"
        ).fetchall()
        high_water = int(rows[-1]["seq"]) if rows else 0
        payload = [dict(row) for row in rows]
        digest = digest_of({"ops": payload})
        quarantined = tuple(
            str(row["op_id"]) for row in rows
            if row["ext"] and row["sup"]  # external lineage + explicit supersedes: ambiguous
        )
    finally:
        conn.close()
    destination.parent.mkdir(parents=True, exist_ok=True)
    export_payload = {
        "manifest": None,
        "ops": payload,
        "note": "synthetic rehearsal export; no raw secrets or personal payloads retained",
    }
    manifest = ExportManifest(
        source_path=str(source.name), source_sha256=sha256_file(source),
        high_water_seq=high_water, tables=tables, rows_digest=digest,
        quarantined=quarantined,
    )
    export_payload["manifest"] = manifest.to_dict()
    destination.write_text(json.dumps(export_payload, sort_keys=True, indent=2), encoding="utf-8")
    return manifest


def map_event(*, source_instance: str, legacy_user: str, legacy_op_id: str) -> dict[str, str]:
    """Namespaced deterministic id; legacy codes become scoped aliases only."""
    raw = f"{source_instance}|{legacy_user}|{legacy_op_id}"
    mapped = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return {
        "op_id": f"mig_{mapped}",
        "fact_id": f"fk_{mapped}",
        "alias_scope": legacy_user,
        "alias": legacy_op_id,
        "valid_from": "unknown",  # never inferred from file mtime or client ts
    }


def reconcile(export_manifest: ExportManifest, accepted: int, quarantined: int) -> dict[str, object]:
    legacy = export_manifest.tables.get("ops", 0)
    accounted = accepted + quarantined
    return {
        "legacy_ops": legacy,
        "accepted": accepted,
        "quarantined": quarantined,
        "unexplained_lost": legacy - accounted,
        "pass": legacy == accounted and export_manifest.high_water_seq <= legacy,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ebrain-migrate", description="E-Brain V3 migration rehearsal tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    export_cmd = sub.add_parser("export", help="Read-only export of a legacy SQLite store")
    export_cmd.add_argument("--source", required=True, help="Path to a synthetic legacy SQLite file")
    export_cmd.add_argument("--out", required=True, help="Destination JSON manifest path")
    sub.add_parser("map-demo", help="Show a deterministic namespaced id mapping (no I/O)")
    recon = sub.add_parser("reconcile", help="Reconcile counts from an export manifest")
    recon.add_argument("--manifest", required=True)
    recon.add_argument("--accepted", type=int, required=True)
    recon.add_argument("--quarantined", type=int, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "export":
        manifest = export(Path(args.source), Path(args.out))
        print(json.dumps(manifest.to_dict(), sort_keys=True))
    elif args.command == "map-demo":
        print(json.dumps(map_event(
            source_instance="synthetic", legacy_user="u1", legacy_op_id="op1",
        ), sort_keys=True))
    elif args.command == "reconcile":
        data = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
        manifest = ExportManifest(**data["manifest"])
        result = reconcile(manifest, args.accepted, args.quarantined)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["pass"] else 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
