"""Traceability: H06."""
from __future__ import annotations

import sqlite3

from ebrain.v3.contracts import digest_of

from tools.ebrain.operations.migrate import export, reconcile


def test_H06_single_writer_reconciliation(tmp_path, pg_ledger, pg_conn):
    source = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(source)
    conn.execute("CREATE TABLE ops(seq INTEGER PRIMARY KEY, user_id TEXT, op_id TEXT, ts INTEGER, "
                 "project TEXT, kind TEXT, path TEXT, auth INTEGER, ext INTEGER, sup INTEGER, "
                 "deleted INTEGER, digest TEXT)")
    for n in range(1, 4):
        conn.execute("INSERT INTO ops VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                     (n, "u1", f"op{n}", n, "p", "claim", "", 2, 0, 0, 0, f"d{n}"))
    conn.commit()
    conn.close()
    manifest = export(source, tmp_path / "export.json")
    assert manifest.rows_digest == digest_of({"ops": manifest_rows(source)})
    result = reconcile(manifest, accepted=3, quarantined=0)
    assert result["pass"] and result["unexplained_lost"] == 0


def manifest_rows(path):
    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute(
        "SELECT seq, user_id, op_id, ts, project, kind, path, auth, ext, sup, deleted, digest "
        "FROM ops ORDER BY seq")]
    conn.close()
    return rows
