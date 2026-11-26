"""HistoryStore: owner-scoped reads and service-side ingest over SQLite (stdlib only).

One store instance is one tenant (``user_id`` is fixed per instance and every statement carries
it) and one connection; open one per request and never share it across requests.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import schema
from .config import DEFAULT_TZ
from .errors import HistoryError
from .models import (DISPLAY_STATUSES, NON_HISTORY_STATES, SORTS, STATES, TERMINAL_STATES, TIERS,
                     TaskIn, display_status, is_verified)

MAX_LIST_LIMIT = 50
PERIOD_CAP = 500
PERIOD_MAX_DAYS = 42
CALENDAR_MAX_DAYS = 366
MAX_QUERY_CHARS = 200
EXPORT_NOTICE = "Read-only task history export. Screenshots are not included."
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EPHEMERAL_SECRET = secrets.token_bytes(32)  # used only when no cursor secret is configured
_VISIBLE = "state NOT IN ('planning','executing')"
_ITEM_COLS = ("task_id, title, subtitle, goal, scenario, state, display_status, tier, "
              "evidence_status, occurred_at, duration_ms, is_sample, result_url, summary")


def _bad(code: str, message: str) -> HistoryError:
    return HistoryError(400, code, message)


def parse_tz(name: str) -> ZoneInfo:
    try:
        if not name or len(name) > 64:
            raise ValueError
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise _bad("invalid_timezone", "Unknown time zone.") from None


def parse_civil(value: str, label: str) -> date:
    if not _DATE_RE.match(value):
        raise _bad("invalid_range", f"'{label}' must be YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise _bad("invalid_range", f"'{label}' is not a valid date.") from None


def civil_to_ms(day: date, tz: ZoneInfo) -> int:
    """UTC epoch milliseconds of local midnight on ``day`` in ``tz``."""
    return int(datetime.combine(day, time.min, tzinfo=tz).timestamp()) * 1000


def ms_to_civil(ms: int, tz: ZoneInfo) -> str:
    return datetime.fromtimestamp(ms // 1000, tz).date().isoformat()


@dataclass(frozen=True)
class Filters:
    q: str = ""
    status: str | None = None
    state: str | None = None
    tier: str | None = None
    from_date: str | None = None
    to_date: str | None = None
    tz: str = DEFAULT_TZ
    include_sample: bool = True
    sort: str = "newest"
    start_ms: int | None = None
    end_ms: int | None = None

    def fingerprint(self) -> str:
        """Binds a cursor to the filters it was issued for."""
        canon = json.dumps([self.q, self.status, self.state, self.tier, self.from_date,
                            self.to_date, self.tz, self.include_sample, self.sort],
                           separators=(",", ":"))
        return hashlib.sha256(canon.encode()).hexdigest()[:16]


def build_filters(*, q: str | None = None, status: str | None = None, state: str | None = None,
                  tier: str | None = None, from_: str | None = None, to: str | None = None,
                  tz: str | None = None, include_sample: str | None = None,
                  sort: str | None = None, require_range: bool = False,
                  max_days: int | None = None) -> Filters:
    """Validates raw query values (raising HistoryError 400) into a Filters."""
    query = (q or "").strip().lower()
    if len(query) > MAX_QUERY_CHARS:
        raise _bad("invalid_param", "Search text is too long.")
    for value, allowed, label in ((status, DISPLAY_STATUSES, "status"), (state, STATES, "state"),
                                  (tier, TIERS, "tier"), (sort, SORTS, "sort")):
        if value is not None and value not in allowed:
            raise _bad("invalid_param", f"Invalid {label}.")
    if include_sample not in (None, "0", "1"):
        raise _bad("invalid_param", "include_sample must be 0 or 1.")
    zone_name = tz or DEFAULT_TZ
    zone = parse_tz(zone_name)
    start = parse_civil(from_, "from") if from_ else None
    end = parse_civil(to, "to") if to else None
    if require_range and (start is None or end is None):
        raise _bad("invalid_range", "'from' and 'to' are required.")
    if start and end:
        days = (end - start).days
        if days <= 0:
            raise _bad("invalid_range", "'to' must be after 'from'.")
        if max_days is not None and days > max_days:
            raise _bad("invalid_range", f"Range is limited to {max_days} days.")
    return Filters(q=query, status=status, state=state, tier=tier, from_date=from_, to_date=to,
                   tz=zone_name, include_sample=include_sample != "0", sort=sort or "newest",
                   start_ms=civil_to_ms(start, zone) if start else None,
                   end_ms=civil_to_ms(end, zone) if end else None)


def encode_cursor(secret: bytes, occurred_at: int, task_id: str, sort: str, fp: str) -> str:
    payload = json.dumps({"o": occurred_at, "i": task_id, "s": sort, "f": fp},
                         separators=(",", ":")).encode()
    raw = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    sig = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}.{sig}"


def decode_cursor(secret: bytes, cursor: str, sort: str, fp: str) -> tuple[int, str]:
    invalid = _bad("invalid_cursor", "Invalid history cursor.")
    parts = cursor.split(".")
    if len(parts) != 2:
        raise invalid
    raw, sig = parts
    expected = hmac.new(secret, raw.encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        raise invalid
    try:
        data = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        occurred, task_id = data["o"], data["i"]
        ok = (isinstance(occurred, int) and not isinstance(occurred, bool)
              and isinstance(task_id, str) and data["s"] == sort and data["f"] == fp)
    except (ValueError, TypeError, KeyError, binascii.Error):
        raise invalid from None
    if not ok:
        raise invalid
    return occurred, task_id


@dataclass(frozen=True)
class IngestResult:
    status: int
    body: dict


def _canonical_hash(value) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _like(q: str) -> str:
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class HistoryStore:
    def __init__(self, data_dir: str, config: dict | None = None, user_id: str = "") -> None:
        if not user_id:
            raise ValueError("user_id must be non-empty")
        self.u = user_id
        self.secret: bytes = (config or {}).get("cursor_secret") or _EPHEMERAL_SECRET
        self.db = schema.connect(data_dir)

    def close(self) -> None:
        self.db.close()

    # ------------------------------------------------------------------ helpers
    def _where(self, f: Filters) -> tuple[str, list]:
        clauses, params = ["user_id = ?", _VISIBLE], [self.u]
        if f.q:
            clauses.append("search_text LIKE ? ESCAPE '\\'")
            params.append(_like(f.q))
        for column, value in (("display_status", f.status), ("state", f.state), ("tier", f.tier)):
            if value is not None:
                clauses.append(f"{column} = ?")
                params.append(value)
        if f.start_ms is not None:
            clauses.append("occurred_at >= ?")
            params.append(f.start_ms)
        if f.end_ms is not None:
            clauses.append("occurred_at < ?")
            params.append(f.end_ms)
        if not f.include_sample:
            clauses.append("is_sample = 0")
        return " AND ".join(clauses), params

    @staticmethod
    def _item(row: sqlite3.Row) -> dict:
        shown_link = is_verified(row["tier"], row["evidence_status"])
        return {
            "task_id": row["task_id"], "title": row["title"], "subtitle": row["subtitle"],
            "goal": row["goal"], "scenario": row["scenario"], "state": row["state"],
            "display_status": row["display_status"], "tier": row["tier"],
            "evidence_status": row["evidence_status"], "occurred_at": row["occurred_at"],
            "duration_ms": row["duration_ms"], "is_sample": bool(row["is_sample"]),
            # Only Tier A (verified) results are ever linked.
            "result_url": row["result_url"] if shown_link else None, "summary": row["summary"],
        }

    # ------------------------------------------------------------------ reads
    def list_tasks(self, f: Filters, *, cursor: str | None = None, limit: int = 20) -> dict:
        limit = max(1, min(limit, MAX_LIST_LIMIT))
        where, params = self._where(f)
        total = self.db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
        newest = f.sort == "newest"
        page_where, page_params = where, list(params)
        if cursor:
            occurred, task_id = decode_cursor(self.secret, cursor, f.sort, f.fingerprint())
            page_where += f" AND (occurred_at, task_id) {'<' if newest else '>'} (?, ?)"
            page_params += [occurred, task_id]
        direction = "DESC" if newest else "ASC"
        rows = self.db.execute(
            f"SELECT {_ITEM_COLS} FROM tasks WHERE {page_where} "
            f"ORDER BY occurred_at {direction}, task_id {direction} LIMIT ?",
            page_params + [limit + 1]).fetchall()
        more = len(rows) > limit
        page = rows[:limit]
        next_cursor = None
        if more and page:
            last = page[-1]
            next_cursor = encode_cursor(self.secret, last["occurred_at"], last["task_id"], f.sort,
                                        f.fingerprint())
        return {"items": [self._item(r) for r in page], "next_cursor": next_cursor,
                "total": total}

    def period(self, f: Filters) -> dict:
        """Every task in [from, to) (capped); day/week/month views must not lose tasks."""
        where, params = self._where(f)
        total = self.db.execute(f"SELECT COUNT(*) FROM tasks WHERE {where}", params).fetchone()[0]
        rows = self.db.execute(
            f"SELECT {_ITEM_COLS} FROM tasks WHERE {where} "
            "ORDER BY occurred_at ASC, task_id ASC LIMIT ?", params + [PERIOD_CAP]).fetchall()
        return {"from": f.from_date, "to": f.to_date, "tz": f.tz,
                "items": [self._item(r) for r in rows], "total": total,
                "truncated": total > PERIOD_CAP}

    def calendar(self, f: Filters) -> dict:
        """Per-day counts, bucketed in the requested zone (SQLite cannot convert IANA zones)."""
        where, params = self._where(f)
        zone = parse_tz(f.tz)
        days: dict[str, dict] = {}
        for row in self.db.execute(
                f"SELECT occurred_at, display_status FROM tasks WHERE {where}", params):
            day = days.setdefault(ms_to_civil(row["occurred_at"], zone),
                                  {"count": 0, "by_status": {}})
            day["count"] += 1
            day["by_status"][row["display_status"]] = (
                day["by_status"].get(row["display_status"], 0) + 1)
        return {"from": f.from_date, "to": f.to_date, "tz": f.tz,
                "days": [{"date": d, **days[d]} for d in sorted(days)]}

    def get_task(self, task_id: str) -> dict | None:
        db, u = self.db, self.u
        row = db.execute(f"SELECT * FROM tasks WHERE user_id = ? AND task_id = ? AND {_VISIBLE}",
                         (u, task_id)).fetchone()
        if row is None:
            return None
        events = [{"seq": r["seq"], "at": r["at"], "type": r["type"], "message": r["message"]}
                  for r in db.execute("SELECT seq, at, type, message FROM task_events "
                                      "WHERE user_id = ? AND task_id = ? ORDER BY seq",
                                      (u, task_id))]
        ev = db.execute("SELECT * FROM task_evidence WHERE user_id = ? AND task_id = ? "
                        "ORDER BY evidence_id LIMIT 1", (u, task_id)).fetchone()
        evidence = None
        if ev is not None:
            evidence = {
                "tier": ev["tier"], "status": ev["status"], "item_id": ev["item_id"],
                # Only Tier A (verified) evidence is ever linked.
                "url": ev["url"] if is_verified(ev["tier"], ev["status"]) else None,
                "readback": ev["readback"], "snapshot_hash": ev["snapshot_hash"],
                "captured_at": ev["captured_at"], "verified_at": ev["verified_at"],
                "expires_at": ev["expires_at"],
            }
        transitions: dict[str, list] = {}
        for t in db.execute(
                "SELECT t.side_effect_id, t.seq, t.at, t.from_state, t.to_state, t.note "
                "FROM side_effect_transitions t JOIN side_effects s "
                "ON s.user_id = t.user_id AND s.side_effect_id = t.side_effect_id "
                "WHERE s.user_id = ? AND s.task_id = ? ORDER BY t.side_effect_id, t.seq",
                (u, task_id)):
            transitions.setdefault(t["side_effect_id"], []).append(
                {"seq": t["seq"], "at": t["at"], "from": t["from_state"], "to": t["to_state"],
                 "note": t["note"]})
        ledger = [{
            "idempotency_key": s["idempotency_key"], "site": s["site"], "target": s["target"],
            "action": s["action"], "payload_hash": s["payload_hash"], "state": s["state"],
            "created_at": s["created_at"], "transitions": transitions.get(s["side_effect_id"], []),
        } for s in db.execute("SELECT * FROM side_effects WHERE user_id = ? AND task_id = ? "
                              "ORDER BY created_at, side_effect_id", (u, task_id))]
        approvals = [{
            "approval_id": a["approval_id"], "page_url": a["page_url"],
            "plan_version": a["plan_version"], "payload_hash": a["payload_hash"],
            "exact_text": a["exact_text"], "decision": a["decision"],
            "decided_at": a["decided_at"], "expires_at": a["expires_at"], "note": a["note"],
        } for a in db.execute("SELECT * FROM approvals WHERE user_id = ? AND task_id = ? "
                              "ORDER BY decided_at, approval_id", (u, task_id))]
        plan = json.loads(row["plan_json"])
        return {
            "task": {
                "task_id": row["task_id"], "title": row["title"], "subtitle": row["subtitle"],
                "goal": row["goal"], "scenario": row["scenario"], "mode": row["mode"],
                "state": row["state"], "display_status": row["display_status"],
                "tier": row["tier"], "evidence_status": row["evidence_status"],
                "revision": row["revision"], "occurred_at": row["occurred_at"],
                "created_at": row["created_at"], "ended_at": row["ended_at"],
                "duration_ms": row["duration_ms"], "attempt": row["attempt"],
                "is_sample": bool(row["is_sample"]), "summary": row["summary"],
                "gate_reason": row["gate_reason"],
            },
            "plan": {"version": row["plan_version"], "hash": row["plan_hash"],
                     "steps": plan.get("steps", []), "sites": plan.get("sites", []),
                     "recipients": plan.get("recipients", [])},
            "events": events, "event_count": len(events), "evidence": evidence,
            "ledger": ledger, "approvals": approvals,
            "artifacts": [],  # screenshots/retention are a later (P2) migration
        }

    def export(self, task_id: str, *, now: int) -> dict | None:
        detail = self.get_task(task_id)
        if detail is None:
            return None
        return {"schema_version": 1, "exported_at": now, "notice": EXPORT_NOTICE,
                "task": detail["task"], "plan": detail["plan"], "events": detail["events"],
                "evidence": detail["evidence"], "ledger": detail["ledger"],
                "approvals": detail["approvals"]}

    # ------------------------------------------------------------------ writes
    @staticmethod
    def _validate(snap: TaskIn) -> str:
        """Semantic checks beyond pydantic. Returns the derived display status."""
        if snap.state in NON_HISTORY_STATES:
            raise _bad("invalid_param", "Planning and executing tasks are not history.")
        if snap.tier == "D" and snap.evidence_status == "verified":
            raise _bad("invalid_param", "Tier D evidence can never be verified.")
        if snap.evidence and (snap.evidence.tier != snap.tier
                              or snap.evidence.status != snap.evidence_status):
            raise _bad("invalid_param", "Evidence must match the task's tier and status.")
        status = display_status(snap.state, snap.tier, snap.evidence_status)
        assert status is not None
        if status == "Verified" and snap.evidence is None:
            raise _bad("invalid_param", "A verified task needs an evidence record.")
        if snap.ended_at is not None and snap.ended_at < snap.created_at:
            raise _bad("invalid_param", "ended_at precedes created_at.")
        if len({e.seq for e in snap.events}) != len(snap.events):
            raise _bad("invalid_param", "Duplicate event seq.")
        if len({li.idempotency_key for li in snap.ledger}) != len(snap.ledger):
            raise _bad("invalid_param", "Duplicate ledger idempotency key.")
        for li in snap.ledger:
            seqs = [t.seq for t in li.transitions if t.seq is not None]
            if len(set(seqs)) != len(seqs):
                raise _bad("invalid_param", "Duplicate ledger transition seq.")
        ids = [a.approval_id for a in snap.approvals if a.approval_id]
        if len(set(ids)) != len(ids):
            raise _bad("invalid_param", "Duplicate approval id.")
        return status

    def ingest(self, snap: TaskIn, *, now: int) -> IngestResult:
        """Create, replay (no-op) or revise a snapshot. See plan §4.2 for the revision table."""
        if snap.user_id != self.u:
            raise _bad("invalid_param", "user_id does not match the store.")
        status = self._validate(snap)
        content_hash = _canonical_hash(snap.model_dump(mode="json", by_alias=True))
        plan = snap.plan.model_dump()
        plan_hash = snap.plan_hash or _canonical_hash({"v": snap.plan_version, "plan": plan})
        duration = None if snap.ended_at is None else snap.ended_at - snap.created_at
        search_text = " ".join([snap.title, snap.subtitle, snap.goal]).lower()
        u, tid, db = self.u, snap.task_id, self.db
        approvals = [(a.approval_id or f"{tid}:ap:{n}", tid, a.page_url, a.plan_version,
                      a.payload_hash, a.exact_text, a.decision, a.decided_at, a.expires_at,
                      a.note) for n, a in enumerate(snap.approvals, 1)]

        db.execute("BEGIN IMMEDIATE")
        try:
            existing = db.execute("SELECT revision, content_hash, state FROM tasks "
                                  "WHERE user_id = ? AND task_id = ?", (u, tid)).fetchone()
            updated = False
            if existing is not None:
                if snap.revision == existing["revision"]:
                    if existing["content_hash"] == content_hash:
                        db.execute("COMMIT")
                        return IngestResult(200, {"created": False, "updated": False,
                                                  "revision": snap.revision})
                    raise HistoryError(409, "conflict", "Same revision, different content.")
                if snap.revision < existing["revision"]:
                    raise HistoryError(409, "conflict", "Stale revision.")
                if existing["state"] in TERMINAL_STATES:
                    raise HistoryError(409, "conflict", "A finished task cannot be rewritten.")
                old = {r["approval_id"]: tuple(r)[1:] for r in db.execute(
                    "SELECT approval_id, task_id, page_url, plan_version, payload_hash, "
                    "exact_text, decision, decided_at, expires_at, note FROM approvals "
                    "WHERE user_id = ? AND task_id = ?", (u, tid))}
                new = {a[0]: a[1:] for a in approvals}
                if any(new.get(aid) != row for aid, row in old.items()):
                    raise HistoryError(409, "conflict",
                                       "A revision may not drop or change an approval.")
                db.execute("DELETE FROM tasks WHERE user_id = ? AND task_id = ?", (u, tid))
                updated = True

            db.execute(
                "INSERT INTO tasks(user_id, task_id, revision, content_hash, goal, title, "
                "subtitle, scenario, mode, state, display_status, tier, evidence_status, "
                "gate_reason, attempt, plan_version, plan_hash, plan_json, device_id, "
                "result_item_id, result_url, snapshot_hash, summary, search_text, is_sample, "
                "occurred_at, created_at, updated_at, ended_at, duration_ms) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (u, tid, snap.revision, content_hash, snap.goal, snap.title, snap.subtitle,
                 snap.scenario, snap.mode, snap.state, status, snap.tier, snap.evidence_status,
                 snap.gate_reason, snap.attempt, snap.plan_version, plan_hash,
                 json.dumps(plan), snap.device_id, snap.result_item_id, snap.result_url,
                 snap.snapshot_hash, snap.summary, search_text, int(snap.is_sample),
                 snap.occurred_at, snap.created_at, now, snap.ended_at, duration))
            db.executemany(
                "INSERT INTO task_events(user_id, task_id, seq, at, type, message) "
                "VALUES(?,?,?,?,?,?)",
                [(u, tid, e.seq, e.at, e.type, e.message) for e in snap.events])
            if snap.evidence is not None:
                ev = snap.evidence
                db.execute(
                    "INSERT INTO task_evidence(user_id, evidence_id, task_id, tier, status, "
                    "item_id, url, readback, snapshot_hash, captured_at, verified_at, "
                    "expires_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (u, f"{tid}:ev:1", tid, ev.tier, ev.status, ev.item_id, ev.url, ev.readback,
                     ev.snapshot_hash, ev.captured_at or snap.created_at, ev.verified_at,
                     ev.expires_at))
            for n, li in enumerate(snap.ledger, 1):
                se_id = f"{tid}:se:{n}"
                created = li.created_at or snap.created_at
                moves = [t.at for t in li.transitions]
                db.execute(
                    "INSERT INTO side_effects(user_id, side_effect_id, task_id, "
                    "idempotency_key, site, target, action, payload_hash, state, created_at, "
                    "updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (u, se_id, tid, li.idempotency_key, li.site, li.target, li.action,
                     li.payload_hash, li.state, created, max(moves + [created])))
                db.executemany(
                    "INSERT INTO side_effect_transitions(user_id, side_effect_id, seq, at, "
                    "from_state, to_state, note) VALUES(?,?,?,?,?,?,?)",
                    [(u, se_id, t.seq or i, t.at, t.from_state, t.to_state, t.note)
                     for i, t in enumerate(li.transitions, 1)])
            db.executemany(
                "INSERT INTO approvals(user_id, approval_id, task_id, page_url, plan_version, "
                "payload_hash, exact_text, decision, decided_at, expires_at, note) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)", [(u, *a) for a in approvals])
            db.execute("COMMIT")
        except HistoryError:
            db.execute("ROLLBACK")
            raise
        except sqlite3.IntegrityError:
            db.execute("ROLLBACK")
            raise HistoryError(409, "conflict", "Snapshot conflicts with stored data.") from None
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        return IngestResult(201 if not updated else 200,
                            {"created": not updated, "updated": updated,
                             "revision": snap.revision})

    def delete_samples(self) -> int:
        """Removes this user's demo (``is_sample=1``) rows only; real history is untouched."""
        return self.db.execute("DELETE FROM tasks WHERE user_id = ? AND is_sample = 1",
                               (self.u,)).rowcount
