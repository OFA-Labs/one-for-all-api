"""Tenant scope (09-test-plan T-015, T-016, T-017, T-091): user_id on every row and statement."""
from ebrain.models import Query, Trace, Write

P = "one-for-all"


def W(op, ts, text, agent="claude", project=P):
    return Write(op, ts, agent, project, "shared", "claim", text)


def codes(s, text, ts=100, project=P):
    return sorted(i.text for i in s.query(Query("q", ts, "claude", project, text, 1024)).items)


EXPECTED_COLUMNS = {
    "ops": ["seq", "user_id", "op_id", "ts", "agent", "project", "vis", "kind", "text", "path", "auth",
            "ext", "sup", "deleted", "digest", "chain", "role", "code", "flags"],
    "codes": ["user_id", "project", "code", "op_id"],
    "terms": ["user_id", "project", "term", "op_id", "chain", "ts", "vis", "agent"],
    "traces": ["user_id", "session_id", "ts", "project", "body"],
    "heal": ["user_id", "project", "op_id", "ts", "action", "reason"],
    "links": ["id", "user_id", "project", "a", "b", "ts", "kind", "score"],
}


def test_T001_schema_matches_02_data_model(ad):
    for table, cols in EXPECTED_COLUMNS.items():
        assert [r[1] for r in ad.db.execute(f"PRAGMA table_info({table})")] == cols, table
    uniques = [r for r in ad.db.execute("PRAGMA index_list(ops)") if r[2]]
    cols = [[c[2] for c in ad.db.execute(f"PRAGMA index_info({u[1]})")] for u in uniques]
    assert ["user_id", "op_id"] in cols


def test_T015_same_op_id_allowed_for_two_users(make_store):
    a, b = make_store(user_id="u-a"), make_store(user_id="u-b")
    assert a.write(W("op-1", 1, "The OTP length is 6 (VC-TENA01).")).accepted
    assert b.write(W("op-1", 1, "The OTP length is 8 (VC-TENB01).")).accepted
    assert codes(a, "OTP length?") == ["The OTP length is 6 (VC-TENA01)."]
    assert codes(b, "OTP length?") == ["The OTP length is 8 (VC-TENB01)."]


def test_T016_rollback_is_scoped_to_user_and_project(make_store):
    a, b = make_store(user_id="u-a"), make_store(user_id="u-b")
    a.write(W("a1", 1, "The OTP length is 6 (VC-TENA11)."))
    a.write(W("a2", 5, "The OTP length is 4 (VC-TENA12)."))
    a.write(W("aj", 5, "The wake word is Jarvis (VC-TENA13).", project="jarvis"))
    b.write(W("b2", 5, "The OTP length is 8 (VC-TENB12)."))
    a.rollback(1, project=P)
    assert codes(a, "OTP length?") == ["The OTP length is 6 (VC-TENA11)."]
    assert codes(a, "wake word?", project="jarvis") == ["The wake word is Jarvis (VC-TENA13)."]
    assert codes(b, "OTP length?") == ["The OTP length is 8 (VC-TENB12)."]
    a.rollback(1)  # all of u-a's projects
    assert codes(a, "wake word?", project="jarvis") == []
    assert b.memory_count(P) == 1


def test_T017_maintain_and_traces_are_scoped_to_user(make_store):
    a = make_store({"heal_mode": "auto"}, user_id="u-a")
    b = make_store({"heal_mode": "auto"}, user_id="u-b")
    for s in (a, b):
        s.write(W("v1", 1, "The VAD silence timeout is 500 ms (VC-TENV01)."))
    a.observe(Trace("sess", 2, "claude", P, ("v1",), (), ("v1",), "Observed 800 ms (VC-TENV09)."))
    assert b.maintain(10).actions == ()  # u-b has no traces
    assert [x["targets"] for x in a.maintain(10).actions] == [["v1"]]
    assert codes(b, "VAD silence timeout?") == ["The VAD silence timeout is 500 ms (VC-TENV01)."]


def test_T091_delete_user_removes_only_that_user(make_store):
    a, b = make_store(user_id="u-a"), make_store(user_id="u-b")
    a.write(W("a1", 1, "The OTP length is 6 (VC-TEND01)."))
    b.write(W("b1", 1, "The OTP length is 8 (VC-TEND02)."))
    assert a.delete_user() >= 1
    assert a.memory_count(P) == 0 and b.memory_count(P) == 1
