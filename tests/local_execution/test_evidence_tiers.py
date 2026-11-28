"""Tier A means the goal was read back. A dispatch receipt is not that."""
import asyncio

from ofa_execution import websites
from ofa_execution.config import LocalConfig
from ofa_execution.contracts import (Evidence, Expectation, Observation, Outcome, Plan, Step,
                                     uid)
from ofa_execution.engine import Engine
from ofa_execution.planner import DeterministicPlanner
from ofa_execution.verification import verify
from ofa_execution.websites import WebsiteHand
from voice.bridge import EngineBridge

from tests.local_execution.test_core import wait

DONE = {"completed", "dispatched", "failed", "unknown"}


def website_engine(monkeypatch, opened=True):
    monkeypatch.setattr(websites, "public_url", lambda raw: raw)
    monkeypatch.setattr(websites.webbrowser, "open", lambda *a, **k: opened)
    config = LocalConfig()
    return Engine(config, {"websites": WebsiteHand(config)}, DeterministicPlanner(config))


def website_plan():
    return Plan(title="open", steps=[Step(operation="website.open", url="https://example.com")])


def test_dispatch_receipt_is_not_completed(monkeypatch):
    engine = website_engine(monkeypatch)
    try:
        task = engine.submit(uid(), website_plan())["task_id"]
        done = wait(engine, task, DONE)
        assert done["state"] == "dispatched", done
        kinds = [e["type"] for e in done["events"]]
        assert "step_dispatched" in kinds
        assert "step_verified" not in kinds and "completed" not in kinds
        evidence = next(e for e in done["events"] if e["type"] == "step_dispatched")["payload"]["evidence"]
        assert [e["tier"] for e in evidence] == ["D"]
    finally:
        engine.close()


def test_refused_dispatch_is_unknown(monkeypatch):
    engine = website_engine(monkeypatch, opened=False)
    try:
        task = engine.submit(uid(), website_plan())["task_id"]
        assert wait(engine, task, DONE)["state"] == "unknown"
    finally:
        engine.close()


def test_failed_assertion_never_carries_tier_a():
    reading = Observation(surface="browser", identity={}, facts={"url": "https://example.com/a"})
    step = Step(operation="browser.observe", expect=Expectation(kind="url", value="https://example.com/b"))
    outcome = verify(step, reading, reading)
    assert outcome.status == "unknown"
    assert not any(e.tier == "A" for e in outcome.evidence)


def test_any_unverified_outcome_loses_tier_a():
    reading = Observation(surface="file", identity={})
    outcome = Outcome(status="unknown", observation=reading,
                      evidence=[Evidence(tier="A", kind="file_readback", reading_hash=reading.hash)])
    assert [(e.tier, e.detail["assertion_matched"]) for e in outcome.evidence] == [("B", False)]


class ClaimsDispatch:
    """Only website.open may finish on a receipt."""
    def capabilities(self):
        return {}

    def observe(self, step):
        return Observation(surface="file", identity={})

    def execute(self, step, before, checkpoint):
        return Outcome(status="dispatched", observation=before)


def test_other_operations_cannot_finish_on_a_receipt(tmp_path):
    config = LocalConfig(read_roots=[str(tmp_path)])
    (tmp_path / "a.txt").write_text("x")
    engine = Engine(config, {"files": ClaimsDispatch()}, DeterministicPlanner(config))
    try:
        step = Step(operation="file.read", target={"path": str(tmp_path / "a.txt")})
        task = engine.submit(uid(), Plan(title="read", steps=[step]))["task_id"]
        assert wait(engine, task, DONE)["state"] == "unknown"
    finally:
        engine.close()


def test_voice_bridge_reports_dispatch_without_calling_it_complete(monkeypatch):
    engine = website_engine(monkeypatch)
    try:
        bridge = EngineBridge(engine)
        assert asyncio.run(bridge.open_url("https://example.com")) is True
        assert bridge.last_snapshot["state"] == "dispatched"
    finally:
        engine.close()
