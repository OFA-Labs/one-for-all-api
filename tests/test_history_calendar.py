"""Calendar and period bucketing in IANA zones, including DST, and their agreement with list."""
from datetime import datetime, timezone

import pytest

import history.store as store_module
from history.models import TaskIn
from history_support import TOKEN_A, auth, make_client, open_store, seed, snapshot

NOW = 1_700_000_000_000


def utc_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()) * 1000


def put(store, task_id: str, utc_iso: str, state="declined"):
    at = utc_ms(utc_iso)
    snap = TaskIn.model_validate(snapshot(user=store.u, task_id=task_id, state=state,
                                          occurred_at=at, created_at=at - 60_000, ended_at=at,
                                          title=task_id))
    store.ingest(snap, now=NOW)


@pytest.fixture
def client(tmp_path):
    store = open_store(tmp_path, "user-a")
    try:
        # 23:30 UTC on Nov 14 is already Nov 15 in Kolkata (+5:30) but still Nov 14 in New York.
        put(store, "late-utc", "2026-11-14T23:30:00")
        put(store, "noon", "2026-11-15T12:00:00")
        # New York leaves DST on 2026-11-01 (06:00 UTC); local Nov 1 lasts 25 hours: 04:00Z-05:00Z+1d.
        put(store, "ny-last-minute", "2026-11-02T04:59:00")
        put(store, "ny-next-day", "2026-11-02T05:00:00")
        put(store, "ny-first", "2026-11-01T04:00:00")
        put(store, "ny-before", "2026-11-01T03:59:00")
    finally:
        store.close()
    return make_client(tmp_path)


def days(client, qs):
    res = client.get("/v1/history/calendar?" + qs, headers=auth(TOKEN_A))
    assert res.status_code == 200, res.text
    return {d["date"]: d["count"] for d in res.json()["days"]}


def test_buckets_follow_the_requested_zone(client):
    base = "from=2026-11-14&to=2026-11-17"
    assert days(client, base + "&tz=UTC") == {"2026-11-14": 1, "2026-11-15": 1}
    assert days(client, base + "&tz=Asia/Kolkata") == {"2026-11-15": 2}
    assert days(client, base + "&tz=America/New_York") == {"2026-11-14": 1, "2026-11-15": 1}
    assert days(client, base + "&tz=Europe/London") == {"2026-11-14": 1, "2026-11-15": 1}


def test_dst_fall_back_day_is_25_hours_in_new_york(client):
    ny = "&tz=America/New_York"
    assert days(client, "from=2026-11-01&to=2026-11-02" + ny) == {"2026-11-01": 2}
    assert days(client, "from=2026-11-02&to=2026-11-03" + ny) == {"2026-11-02": 1}
    # 03:59Z is 23:59 EDT on Oct 31, the day before.
    assert days(client, "from=2026-10-31&to=2026-11-01" + ny) == {"2026-10-31": 1}


@pytest.mark.parametrize("tz", ["Asia/Kolkata", "UTC", "America/New_York", "Europe/London"])
def test_calendar_period_and_list_agree(client, tz):
    qs = f"from=2026-10-30&to=2026-11-20&tz={tz.replace('/', '%2F')}"
    cal = client.get("/v1/history/calendar?" + qs, headers=auth(TOKEN_A)).json()
    period = client.get("/v1/history/period?" + qs, headers=auth(TOKEN_A)).json()
    listing = client.get("/v1/tasks?" + qs + "&limit=50", headers=auth(TOKEN_A)).json()
    assert sum(d["count"] for d in cal["days"]) == period["total"] == listing["total"] == 6
    assert [i["task_id"] for i in period["items"]] == sorted(
        (i["task_id"] for i in listing["items"]),
        key=lambda t: [x["occurred_at"] for x in listing["items"] if x["task_id"] == t][0])
    # every day's count equals what the period endpoint returns for that single day
    for day in cal["days"]:
        nxt = datetime.fromisoformat(day["date"]).toordinal() + 1
        end = datetime.fromordinal(nxt).date().isoformat()
        one = client.get(f"/v1/history/period?from={day['date']}&to={end}&tz={tz.replace('/', '%2F')}",
                         headers=auth(TOKEN_A)).json()
        assert one["total"] == day["count"], (tz, day)


def test_calendar_by_status_and_filters(tmp_path):
    seed(tmp_path, "user-a")
    client = make_client(tmp_path)
    res = client.get("/v1/history/calendar?from=2026-11-01&to=2026-12-01&tz=Asia/Kolkata",
                     headers=auth(TOKEN_A)).json()
    assert res["tz"] == "Asia/Kolkata" and res["from"] == "2026-11-01"
    assert res["days"] == [
        {"date": "2026-11-14", "count": 2, "by_status": {"Paused": 1, "Unknown": 1}},
        {"date": "2026-11-15", "count": 3,
         "by_status": {"Verified": 1, "Submitted": 1, "Declined": 1}},
        {"date": "2026-11-16", "count": 2, "by_status": {"Verified": 1, "Needs review": 1}},
    ]
    only = client.get("/v1/history/calendar?from=2026-11-01&to=2026-12-01&status=Verified",
                      headers=auth(TOKEN_A)).json()
    assert [d["date"] for d in only["days"]] == ["2026-11-15", "2026-11-16"]
    assert client.get("/v1/history/calendar?from=2026-11-01&to=2026-12-01&q=zzz",
                      headers=auth(TOKEN_A)).json()["days"] == []


def test_range_and_zone_validation(client):
    for qs, code in (("from=2026-01-01&to=2027-01-03&tz=UTC", "invalid_range"),  # 367 days
                     ("from=2026-01-01&tz=UTC", "invalid_range"),
                     ("to=2026-01-01", "invalid_range"),
                     ("from=2026-01-02&to=2026-01-01", "invalid_range"),
                     ("from=2026-01-01&to=2026-01-02&tz=Nope/Zone", "invalid_timezone")):
        res = client.get("/v1/history/calendar?" + qs, headers=auth(TOKEN_A))
        assert res.status_code == 400 and res.json()["error"]["code"] == code, qs
    ok = client.get("/v1/history/calendar?from=2026-01-01&to=2027-01-02&tz=UTC",
                    headers=auth(TOKEN_A))
    assert ok.status_code == 200  # exactly 366 days


def test_period_limits(client, monkeypatch):
    base = "/v1/history/period?"
    res = client.get(base + "from=2026-01-01&to=2026-02-12", headers=auth(TOKEN_A))
    assert res.status_code == 200  # exactly 42 days
    res = client.get(base + "from=2026-01-01&to=2026-02-13", headers=auth(TOKEN_A))
    assert res.status_code == 400 and res.json()["error"]["code"] == "invalid_range"
    monkeypatch.setattr(store_module, "PERIOD_CAP", 2)
    res = client.get(base + "from=2026-10-30&to=2026-11-20&tz=UTC", headers=auth(TOKEN_A)).json()
    assert res["total"] == 6 and len(res["items"]) == 2 and res["truncated"] is True
    assert [i["task_id"] for i in res["items"]] == ["ny-before", "ny-first"]  # oldest first
    full = client.get(base + "from=2026-11-14&to=2026-11-16&tz=UTC", headers=auth(TOKEN_A)).json()
    assert full["truncated"] is False and full["total"] == 2


def test_period_order_is_chronological(client):
    res = client.get("/v1/history/period?from=2026-10-30&to=2026-11-20&tz=UTC",
                     headers=auth(TOKEN_A)).json()
    times = [i["occurred_at"] for i in res["items"]]
    assert times == sorted(times)
