"""Individual-use encrypted backup and isolated restore drill.

AES-256-GCM with a synthetic in-process key (never written or printed); owner
key custody remains a separate action. Uses only the disposable test database.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

API = Path(__file__).resolve().parents[3]
CONTAINER = "ebrain-v3-test-pg"
SRC_DB = "ebrain_v3_test"
RESTORE_DB = "ebrain_v3_restore_drill"
OUT = API / "docs/ebrain/implementation-plan/evidence/backup-drill"


def admin_password() -> str:
    raw = subprocess.run(
        ["docker", "inspect", CONTAINER, "--format",
         "{{range .Config.Env}}{{println .}}{{end}}"],
        capture_output=True, text=True, check=True,
    ).stdout
    match = re.search(r"^POSTGRES_PASSWORD=(.+)$", raw, re.M)
    if not match:
        raise RuntimeError("bootstrap password unavailable")
    return match.group(1)


def psql(sql: str, *, db: str = SRC_DB) -> str:
    env = dict(os.environ)
    env["PGPASSWORD"] = admin_password()
    result = subprocess.run(
        ["docker", "exec", "-e", "PGPASSWORD", CONTAINER,
         "psql", "-U", "ebrain_admin", "-d", db, "-Atqc", sql],
        env=env, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(prog="backup-drill")
    parser.add_argument("--key-file", default=str(
        Path(tempfile.gettempdir()) / "opencode" / "ebrain-v3-backup.key"))
    parser.add_argument("--rotate-key", action="store_true")
    args = parser.parse_args()
    utc = datetime.datetime.now(datetime.timezone.utc)
    run_id = utc.strftime("%Y%m%dT%H%M%SZ") + "-backup-drill"
    OUT.mkdir(parents=True, exist_ok=True)
    key_file = Path(args.key_file)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if args.rotate_key or not key_file.exists():
        key = AESGCM.generate_key(bit_length=256)
        key_file.write_bytes(key)
        try:
            os.chmod(key_file, 0o600)
        except OSError:
            pass
    else:
        key = key_file.read_bytes()
    acl_status = "not_applicable"
    if os.name == "nt":
        user = os.environ.get("USERNAME", "")
        if user:
            proc = subprocess.run(
                ["icacls", str(key_file), "/inheritance:r", "/grant:r",
                 f"{user}:(F)"],
                capture_output=True, text=True,
            )
            acl_status = "restricted_to_current_user" if proc.returncode == 0 else "acl_failed"
    key_id = hashlib.sha256(key).hexdigest()[:16]
    nonce = os.urandom(12)

    env = dict(os.environ)
    env["PGPASSWORD"] = admin_password()
    dump = subprocess.run(
        ["docker", "exec", "-e", "PGPASSWORD", CONTAINER,
         "pg_dump", "-U", "ebrain_admin", "-d", SRC_DB, "-Fc"],
        env=env, capture_output=True, check=True,
    ).stdout
    ciphertext = AESGCM(key).encrypt(nonce, dump, b"ebrain-v3-individual")
    temp = Path(tempfile.gettempdir()) / "opencode" / "ebrain-backup"
    temp.mkdir(parents=True, exist_ok=True)
    blob = temp / "backup.bin"
    blob.write_bytes(nonce + ciphertext)

    source_counts = {
        table: int(psql(f"SELECT count(*) FROM {table}") or 0)
        for table in ("v3_event", "v3_claim", "v3_receipt", "v3_outbox")
    }
    # Isolated restore into a separate disposable database.
    psql(f'DROP DATABASE IF EXISTS "{RESTORE_DB}"', db="postgres")
    psql(f'CREATE DATABASE "{RESTORE_DB}"', db="postgres")
    restored = AESGCM(key).decrypt(nonce, ciphertext, b"ebrain-v3-individual")
    env2 = dict(os.environ)
    env2["PGPASSWORD"] = admin_password()
    result = subprocess.run(
        ["docker", "exec", "-i", "-e", "PGPASSWORD", CONTAINER,
         "pg_restore", "-U", "ebrain_admin", "-d", RESTORE_DB, "--no-owner"],
        input=restored, env=env2, capture_output=True,
    )
    if result.returncode != 0:
        tail = result.stderr.decode("utf-8", "replace")[-800:]
        raise RuntimeError(f"pg_restore failed: {tail}")
    restored_counts = {
        table: int(psql(f"SELECT count(*) FROM {table}", db=RESTORE_DB) or 0)
        for table in source_counts
    }
    policies = int(psql(
        "SELECT count(*) FROM pg_policies WHERE schemaname='public' AND tablename LIKE 'v3_%'",
        db=RESTORE_DB,
    ) or 0)
    psql(f'DROP DATABASE IF EXISTS "{RESTORE_DB}"', db="postgres")
    blob.unlink()

    manifest = {
        "run_id": run_id,
        "utc": utc.isoformat(),
        "algorithm": "AES-256-GCM",
        "key_id": key_id,
        "key_handling": (
            "AES-256 key stored outside the synced workspace in a restricted local "
            "file; key bytes never printed or written to evidence"
        ),
        "key_file_location": str(key_file.parent),
        "key_file_acl": acl_status,
        "key_id": key_id,
        "plaintext_sha256": hashlib.sha256(dump).hexdigest(),
        "ciphertext_sha256": hashlib.sha256(nonce + ciphertext).hexdigest(),
        "dump_bytes": len(dump),
        "encrypted_bytes": len(nonce + ciphertext),
        "source_counts": source_counts,
        "restored_counts": restored_counts,
        "counts_match": source_counts == restored_counts,
        "restored_rls_policies": policies,
        "restore_pass": source_counts == restored_counts and policies == 15,
        "evidence_dir": str(OUT / run_id),
    }
    (OUT / run_id).mkdir(parents=True, exist_ok=True)
    (OUT / run_id / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in manifest.items() if k != "key_id"}, indent=2))
    return 0 if manifest["restore_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
