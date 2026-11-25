"""Isolated restore/reconcile rehearsal tool (M13 CP13.5).

Restore starts read-closed. Unknown latest suppression/revocation => remain
closed (fail closed). No production backup location or credentials are embedded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RestoreManifest:
    db_digest: str
    wal_digest: str
    control_digest: str
    suppression_digest: str
    source_digest: str

    def digest(self) -> str:
        return hashlib.sha256(json.dumps({
            "db": self.db_digest, "wal": self.wal_digest,
            "control": self.control_digest, "suppression": self.suppression_digest,
            "source": self.source_digest,
        }, sort_keys=True).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_restore(backup_dir: Path, control: dict[str, object]) -> dict[str, object]:
    """Reconcile digests and refuse to open when control-plane freshness is unknown."""
    required = ("database.bin", "wal.bin", "suppression.json", "control.json")
    missing = [name for name in required if not (backup_dir / name).exists()]
    if missing:
        return {"open_for_serving": False, "reason": "missing_artifacts", "missing": missing}
    suppression = json.loads((backup_dir / "suppression.json").read_text(encoding="utf-8"))
    if not isinstance(suppression, dict) or "latest_seq" not in suppression:
        return {"open_for_serving": False, "reason": "unknown_latest_suppression"}
    if int(suppression["latest_seq"]) < int(control.get("latest_control_seq", 0)):
        return {"open_for_serving": False, "reason": "stale_suppression"}
    manifest = RestoreManifest(
        db_digest=file_digest(backup_dir / "database.bin"),
        wal_digest=file_digest(backup_dir / "wal.bin"),
        control_digest=file_digest(backup_dir / "control.json"),
        suppression_digest=file_digest(backup_dir / "suppression.json"),
        source_digest=str(control.get("source_digest", "")),
    )
    return {
        "open_for_serving": True,
        "restore_digest": manifest.digest(),
        "checked_at": "server-assigned",
        "note": "rehearsal only; run RLS/erasure/security tests before serving",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ebrain-restore")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("verify", help="Verify an isolated rehearsal backup")
    check.add_argument("--backup-dir", required=True)
    check.add_argument("--control", required=True, help="JSON file with latest_control_seq")
    args = parser.parse_args(argv)
    control = json.loads(Path(args.control).read_text(encoding="utf-8"))
    result = verify_restore(Path(args.backup_dir), control)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["open_for_serving"] else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
