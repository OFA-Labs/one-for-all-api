"""History DDL and migrations (``PRAGMA user_version``). SQLite-specific by design.

Every table is keyed by ``(user_id, task_id)``: task ids are never global, so two users may each
hold ``sample-pr`` and no response can reveal another user's ids. The artifacts table is a later
(P2) migration and is intentionally absent from version 1.
"""
from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

DDL_V1 = """
CREATE TABLE IF NOT EXISTS tasks (
  user_id          TEXT NOT NULL,
  task_id          TEXT NOT NULL,
  revision         INTEGER NOT NULL DEFAULT 1 CHECK (revision >= 1),
  content_hash     TEXT NOT NULL,
  goal             TEXT NOT NULL,
  title            TEXT NOT NULL,
  subtitle         TEXT NOT NULL DEFAULT '',
  scenario         TEXT NOT NULL DEFAULT 'unknown',
  mode             TEXT NOT NULL DEFAULT 'personal' CHECK (mode IN ('personal', 'playground')),
  state            TEXT NOT NULL
                     CHECK (state IN ('planning','executing','waiting','permission','question',
                                      'paused','completed','declined','cancelled','error',
                                      'unknown')),
  display_status   TEXT NOT NULL
                     CHECK (display_status IN ('Verified','Needs review','Submitted','Declined',
                                               'Paused','Cancelled','Unknown','Error')),
  tier             TEXT NOT NULL DEFAULT 'none'
                     CHECK (tier IN ('A','B','C','D','unknown','none')),
  evidence_status  TEXT NOT NULL DEFAULT 'none'
                     CHECK (evidence_status IN ('verified','submitted','held','unknown','none')),
  gate_reason      TEXT,
  attempt          INTEGER NOT NULL DEFAULT 1 CHECK (attempt >= 1),
  plan_version     INTEGER NOT NULL DEFAULT 1 CHECK (plan_version >= 1),
  plan_hash        TEXT NOT NULL,
  plan_json        TEXT NOT NULL,
  device_id        TEXT,
  result_item_id   TEXT,
  result_url       TEXT,
  snapshot_hash    TEXT,
  summary          TEXT,
  search_text      TEXT NOT NULL,
  is_sample        INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0,1)),
  occurred_at      INTEGER NOT NULL,
  created_at       INTEGER NOT NULL,
  updated_at       INTEGER NOT NULL,
  ended_at         INTEGER,
  duration_ms      INTEGER,
  PRIMARY KEY (user_id, task_id)
);
CREATE INDEX IF NOT EXISTS tasks_owner_time ON tasks(user_id, occurred_at DESC, task_id DESC);
CREATE INDEX IF NOT EXISTS tasks_owner_status ON tasks(user_id, display_status, occurred_at DESC);
CREATE INDEX IF NOT EXISTS tasks_owner_state ON tasks(user_id, state, occurred_at DESC);

CREATE TABLE IF NOT EXISTS task_events (
  user_id       TEXT NOT NULL,
  task_id       TEXT NOT NULL,
  seq           INTEGER NOT NULL CHECK (seq >= 1),
  at            INTEGER NOT NULL,
  type          TEXT NOT NULL,
  message       TEXT NOT NULL,
  payload_json  TEXT,
  PRIMARY KEY (user_id, task_id, seq),
  FOREIGN KEY (user_id, task_id) REFERENCES tasks(user_id, task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_evidence (
  user_id        TEXT NOT NULL,
  evidence_id    TEXT NOT NULL,
  task_id        TEXT NOT NULL,
  tier           TEXT NOT NULL CHECK (tier IN ('A','B','C','D','unknown','none')),
  status         TEXT NOT NULL CHECK (status IN ('verified','submitted','held','unknown','none')),
  item_id        TEXT,
  url            TEXT,
  readback       TEXT,
  snapshot_hash  TEXT,
  captured_at    INTEGER NOT NULL,
  verified_at    INTEGER,
  expires_at     INTEGER,
  PRIMARY KEY (user_id, evidence_id),
  FOREIGN KEY (user_id, task_id) REFERENCES tasks(user_id, task_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS task_evidence_task ON task_evidence(user_id, task_id);

CREATE TABLE IF NOT EXISTS approvals (
  user_id        TEXT NOT NULL,
  approval_id    TEXT NOT NULL,
  task_id        TEXT NOT NULL,
  page_url       TEXT NOT NULL,
  plan_version   INTEGER NOT NULL,
  payload_hash   TEXT NOT NULL,
  exact_text     TEXT NOT NULL,
  decision       TEXT NOT NULL CHECK (decision IN ('approved','rejected','expired','revoked')),
  decided_at     INTEGER NOT NULL,
  expires_at     INTEGER,
  note           TEXT,
  PRIMARY KEY (user_id, approval_id),
  FOREIGN KEY (user_id, task_id) REFERENCES tasks(user_id, task_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS approvals_task ON approvals(user_id, task_id, decided_at);

CREATE TABLE IF NOT EXISTS side_effects (
  user_id           TEXT NOT NULL,
  side_effect_id    TEXT NOT NULL,
  task_id           TEXT NOT NULL,
  idempotency_key   TEXT NOT NULL,
  site              TEXT NOT NULL,
  target            TEXT,
  action            TEXT NOT NULL,
  payload_hash      TEXT NOT NULL,
  state             TEXT NOT NULL
                      CHECK (state IN ('intent','committed','verified','unknown','failed')),
  evidence_id       TEXT,
  created_at        INTEGER NOT NULL,
  updated_at        INTEGER NOT NULL,
  PRIMARY KEY (user_id, side_effect_id),
  UNIQUE (user_id, task_id, idempotency_key),
  FOREIGN KEY (user_id, task_id) REFERENCES tasks(user_id, task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS side_effect_transitions (
  user_id         TEXT NOT NULL,
  side_effect_id  TEXT NOT NULL,
  seq             INTEGER NOT NULL CHECK (seq >= 1),
  at              INTEGER NOT NULL,
  from_state      TEXT,
  to_state        TEXT NOT NULL,
  note            TEXT,
  PRIMARY KEY (user_id, side_effect_id, seq),
  FOREIGN KEY (user_id, side_effect_id)
    REFERENCES side_effects(user_id, side_effect_id) ON DELETE CASCADE
);

CREATE TRIGGER IF NOT EXISTS approvals_no_update
BEFORE UPDATE ON approvals
BEGIN SELECT RAISE(ABORT, 'approvals are append-only'); END;
"""

# Applied in order; each entry upgrades user_version to its index + 1. Never auto-drops.
MIGRATIONS = (DDL_V1,)


def connect(data_dir: str, filename: str = "history.sqlite") -> sqlite3.Connection:
    """Opens (creating/migrating if needed) the History database. One connection per request."""
    import os

    os.makedirs(data_dir, exist_ok=True)
    # check_same_thread=False: FastAPI may open a dependency and run the endpoint on different
    # worker threads. The connection is still used by exactly one request at a time.
    db = sqlite3.connect(os.path.join(data_dir, filename), timeout=60, isolation_level=None,
                         check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=60000")
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=ON")
    migrate(db)
    return db


def schema_version(db: sqlite3.Connection) -> int:
    return db.execute("PRAGMA user_version").fetchone()[0]


def migrate(db: sqlite3.Connection) -> None:
    current = schema_version(db)
    if current > SCHEMA_VERSION:
        raise RuntimeError("history database is newer than this code")
    for version in range(current, SCHEMA_VERSION):
        # executescript issues its own COMMIT first; BEGIN IMMEDIATE serialises concurrent
        # openers and every statement is IF NOT EXISTS, so a lost race is a harmless re-run.
        db.executescript("BEGIN IMMEDIATE;\n" + MIGRATIONS[version]
                         + f"\nPRAGMA user_version={version + 1};\nCOMMIT;")
