"""V1–V3 egress canaries; A13 audit chain and redaction; Q2 purge."""
import base64
import logging
from urllib.parse import quote

import pytest

from ofa.audit import Audit
from ofa.egress import EGRESS, Egress, LeakBlocked, RedactingFilter


def test_registered_secret_blocked_in_all_encodings():
    e = Egress()
    secret = "Hunter2-Sup3r!secret"
    e.register(secret)
    for payload in (secret, f"pwd={secret}", secret.lower(), quote(secret, safe=""),
                    base64.b64encode(secret.encode()).decode(), secret.encode().hex(), secret[::-1],
                    {"messages": [{"content": f"x {secret} y"}]}, f"{secret}".encode()):
        with pytest.raises(LeakBlocked):
            e.guard(payload, "llm")
    assert e.guard("nothing sensitive here", "llm") == "nothing sensitive here"


def test_canary_blocks_and_alerts():
    e = Egress()
    hits = []
    e.on_alert = hits.append
    c = e.canary()
    with pytest.raises(LeakBlocked):
        e.guard({"tool_result": c}, "llm")
    assert hits == ["llm"] and e.alerts[-1]["label"] == "canary"


def test_log_filter_blocks_secret_lines(caplog):
    EGRESS.register("LogSecretValue-991")
    logger = logging.getLogger("ofa.test.log")
    logger.addFilter(RedactingFilter())
    with caplog.at_level(logging.INFO):
        logger.info("token is %s", "LogSecretValue-991")
    assert "LogSecretValue-991" not in caplog.text
    assert "blocked" in caplog.text
    EGRESS.forget_all()


def test_audit_chain_and_redaction(tmp_path):
    a = Audit(tmp_path)
    a.write("approval_granted", epoch=1, digest="d" * 64, handle_ids=["vault:D3/github/password#1"], result="ok")
    a.write("action", epoch=1, tier=2, result="verified", password="should-not-appear")
    text = "".join(p.read_text() for p in tmp_path.glob("*.jsonl"))
    assert "should-not-appear" not in text and a.verify_chain()
    EGRESS.register("AuditLeak-12345")
    a.write("action", detail="AuditLeak-12345")
    text = "".join(p.read_text() for p in tmp_path.glob("*.jsonl"))
    assert "AuditLeak-12345" not in text and "redacted_leak_blocked" in text and a.verify_chain()
    EGRESS.forget_all()


def test_audit_tamper_detected(tmp_path):
    a = Audit(tmp_path)
    for i in range(3):
        a.write("x", result=str(i))
    f = next(tmp_path.glob("*.jsonl"))
    lines = f.read_text().splitlines()
    lines[1] = lines[1].replace('"1"', '"9"')
    f.write_text("\n".join(lines) + "\n")
    assert not a.verify_chain()


def test_audit_purge(tmp_path):
    a = Audit(tmp_path)
    (tmp_path / "2000-01.jsonl").write_text('{"kind":"old"}\n')
    a.write("x")
    assert a.purge("2001-01") == 1
    assert not (tmp_path / "2000-01.jsonl").exists()
