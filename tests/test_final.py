"""FINAL changes F1-F4 (09-test-plan T-010, T-020, T-022, T-030..T-033, T-040, T-041, T-043, T-044)."""
from ebrain.models import Query, Trace, Write
from ebrain.store import UnknownTarget, _trigram_cosine

P = "one-for-all"


def W(op, ts, text, agent="claude", **kw):
    return Write(op, ts, agent, P, kw.pop("visibility", "shared"), kw.pop("kind", "claim"), text, **kw)


def cur(ad, text, ts=100, agent="claude"):
    b = ad.query(Query("q", ts, agent, P, text, 1024))
    return {i.item_id: i for i in b.items if i.status == "current"}, b


def test_T010_private_supersession_invisible_to_other_agent(ad):
    ad.write(W("s1", 1, "The wake word is Jarvis (VC-WAKE01)."))
    ad.write(W("p1", 2, "The wake word is Computer (VC-WAKE02).", visibility="private"))
    seen_codex, _ = cur(ad, "wake word?", agent="codex")
    seen_claude, _ = cur(ad, "wake word?", agent="claude")
    assert "s1" in seen_codex and "p1" not in seen_codex
    assert "p1" in seen_claude and "s1" not in seen_claude


def test_T020_capacity_states(make_store):
    ad = make_store({"capacity_soft": 3, "capacity_hard": 5})
    for i in range(4):
        ad.write(W(f"n{i}", i, f"Note {i} about the OTP length is {i} (VC-CAPA0{i})."))
    assert ad.limits(P)["capacity_state"] == "near_limit"
    for i in range(4, 7):
        ad.write(W(f"n{i}", i, f"Note {i} about the OTP length is {i} (VC-CAPA0{i})."))
    assert ad.limits(P) == {"memory_count": 7, "capacity_soft": 3, "capacity_hard": 5,
                            "capacity_state": "beyond_tested_range", "heal_mode": "propose",
                            "subject_join": "off"}


def test_T021_capacity_reject_mode(make_store):
    ad = make_store({"capacity_hard": 1, "capacity_soft": 1, "capacity_mode": "reject"})
    assert ad.write(W("a", 1, "The OTP length is 6 (VC-OTPR01).")).accepted
    ack = ad.write(W("b", 2, "The OTP length is 8 (VC-OTPR02)."))
    assert (ack.accepted, ack.reason) == (False, "capacity exceeded")


def test_T022_beyond_range_is_never_silent(make_store):
    ad = make_store({"capacity_hard": 1, "capacity_soft": 1})
    ad.write(W("a", 1, "The OTP length is 6 (VC-OTPA01)."))
    ad.write(W("b", 2, "The OTP length is 8 (VC-OTPA02)."))
    items, b = cur(ad, "OTP length?")
    assert items and all("beyond_tested_range" in i.flags for i in items.values())
    assert "beyond tested range" in b.rendered


def _stale_trace(ad):
    ad.write(W("v1", 1, "The VAD silence timeout is 500 ms (VC-VADA01)."))
    ad.observe(Trace("s1", 5, "claude", P, shown=("v1",), ignored=("v1",),
                     note="Observed VAD timeout 800 ms in config (VC-VADA09)."))


def test_T030_default_heal_is_proposal_only(ad):
    _stale_trace(ad)
    assert [a["action"] for a in ad.maintain(10).actions] == ["propose_demote"]
    assert "v1" in cur(ad, "VAD silence timeout?")[0]
    assert [p["op_id"] for p in ad.heal_state(P)["proposals"]] == ["v1"]


def test_T031_human_approval_applies_and_rolls_back(ad):
    _stale_trace(ad)
    ad.maintain(10)
    ad.approve_heal("v1", 11)
    assert "v1" not in cur(ad, "VAD silence timeout?", ts=12)[0]
    assert ad.heal_state(P)["proposals"] == []
    ad.rollback(10)
    assert "v1" in cur(ad, "VAD silence timeout?", ts=12)[0]


def test_T032_heal_off(make_store):
    ad = make_store({"heal_mode": "off"})
    _stale_trace(ad)
    assert ad.maintain(10).actions == ()


def test_T033_approve_unknown_raises(ad):
    try:
        ad.approve_heal("nope", 1)
    except UnknownTarget:
        return
    raise AssertionError("expected UnknownTarget")


def test_T040_subject_join_off_by_default_never_links(ad):
    ad.write(W("a1", 1, "The auth token TTL is 45 minutes (VC-JOIN01)."))
    ad.write(W("a2", 2, "Access token lifetime: now 30 minutes [VC-JOIN02]"))
    assert ad.possible_pairs(P, "claude", 10) == []


def test_T041_trigram_similarity_orders_rewording_above_unrelated():
    same = _trigram_cosine({"auth", "token", "ttl"}, {"auth", "token", "ttl", "minute"})
    other = _trigram_cosine({"auth", "token", "ttl"}, {"vercel", "plan", "hobby"})
    assert same > 0.6 > other


def test_T043_review_band_flags_pair_and_human_confirms(make_store):
    ad = make_store({"subject_join": "on", "join_auto_threshold": 0.99, "join_review_threshold": 0.05})
    ad.write(W("a1", 1, "The auth token TTL is 45 minutes (VC-JOIN01)."))
    ad.write(W("a2", 2, "Access token lifetime: now 30 minutes [VC-JOIN02]"))
    pairs = ad.possible_pairs(P, "claude", 10)
    assert len(pairs) == 1
    items, _ = cur(ad, "access token lifetime auth TTL")
    assert all("possible_same_fact" in i.flags for i in items.values()) and len(items) == 2
    ad.confirm_same(P, pairs[0]["a"], pairs[0]["b"], 3)
    items, _ = cur(ad, "access token lifetime auth TTL")
    assert list(items) == ["a2"]
    ad.split_same(P, pairs[0]["a"], pairs[0]["b"], 4)
    assert len(cur(ad, "access token lifetime auth TTL")[0]) == 2
    ad.rollback(2)
    assert len(ad.possible_pairs(P, "claude", 10)) == 1


def test_T044_review_band_never_auto_merges_near_miss(make_store):
    ad = make_store({"subject_join": "on"})
    ad.write(W("a1", 1, "The auth token TTL is 45 minutes (VC-NEAR01)."))
    ad.write(W("r1", 2, "The refresh token TTL is 7 days (VC-NEAR02)."))
    assert len(cur(ad, "auth refresh token TTL")[0]) == 2


def test_T014_chains_and_versions_for_ui(ad):
    ad.write(W("a1", 1, "The auth token TTL is 45 minutes (VC-UIAA01)."))
    ad.write(W("a2", 2, "Changed auth-token TTL to 30 minutes per QA feedback (VC-UIAA02)."))
    rows = ad.chains(P, "claude", 10)
    assert len(rows) == 1 and rows[0]["head"]["op_id"] == "a2" and rows[0]["versions"] == 2
    vs = ad.chain_versions(P, rows[0]["chain"], "claude", 10)
    assert [(v["op_id"], v["status"], v["silent"]) for v in vs] == [
        ("a1", "superseded", True), ("a2", "current", True)]
