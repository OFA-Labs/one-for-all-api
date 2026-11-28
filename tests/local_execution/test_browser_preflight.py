"""Nothing is clicked unless the click would land on it; only the checks are retried."""
import pytest

from ofa_execution import browser
from ofa_execution.browser import ACT, COLLECT, PREFLIGHT, BrowserHand
from ofa_execution.config import LocalConfig
from ofa_execution.contracts import Expectation, ExecutionError, Plan, Step, Target, uid
from ofa_execution.engine import Engine
from ofa_execution.planner import DeterministicPlanner

from tests.local_execution.test_core import approve, wait

ORIGIN = "https://example.com"
DONE = {"completed", "failed", "unknown", "cancelled"}
GOOD = {"found": True, "stable": True, "hit_target": True}
MOVING = {**GOOD, "stable": False}
COVERED = {**GOOD, "hit_target": False}


class FakeMcp:
    def __init__(self, preflights, act_error=None):
        self.preflights, self.act_error = list(preflights), act_error
        self.acts, self.checks, self.clicked = 0, 0, False

    def call(self, name, arguments):
        expression = arguments["expression"]
        if expression == COLLECT:
            return {"surface": "browser", "identity": {"document": "d"},
                    "elements": [{"ref": "d:1", "name": "Send", "role": "button", "bounds": [0, 0, 10, 10]}],
                    "facts": {"url": ORIGIN + "/", "title": "Sent" if self.clicked else "Ready"}}
        if expression == PREFLIGHT:
            self.checks += 1
            return self.preflights.pop(0) if len(self.preflights) > 1 else self.preflights[0]
        assert expression == ACT
        self.acts += 1
        if self.act_error:
            raise self.act_error
        self.clicked = True
        return True


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(browser, "RETRY_WAITS", (0,) * len(browser.RETRY_WAITS))


def click(tmp_path, client):
    config = LocalConfig(allowed_origins=[ORIGIN], ledger_dir=str(tmp_path / "ledger"))
    hand = BrowserHand(config, client)
    hand.tabs, hand.last_tab = {"1": ORIGIN}, "1"
    engine = Engine(config, {"browser": hand}, DeterministicPlanner(config))
    step = Step(operation="browser.click", target=Target(name="Send"), expect=Expectation(kind="changed"))
    task = engine.submit(uid(), Plan(title="click", steps=[step], allowed_origins=[ORIGIN]))["task_id"]
    snap = wait(engine, task, {"approval"} | DONE)
    assert snap["state"] == "approval", snap["error"]
    approve(engine, task, snap)
    done = wait(engine, task, DONE)
    return engine, step, done


def test_retry_schedule_is_the_agreed_one():
    import importlib
    assert importlib.reload(browser).RETRY_WAITS == (0, 0.02, 0.1, 0.1, 0.5)


@pytest.mark.parametrize("reading,code", [(COVERED, "HIT_TARGET_INTERCEPTED"), (MOVING, "ELEMENT_UNSTABLE"),
                                          ({"found": False}, "TARGET_NOT_FOUND"), ("junk", "BROWSER_SCHEMA_CHANGED"),
                                          ({"found": True, "stable": True}, "HIT_TARGET_INTERCEPTED")])
def test_failed_preflight_sends_nothing(tmp_path, reading, code):
    client = FakeMcp([reading])
    engine, step, done = click(tmp_path, client)
    try:
        assert done["error"]["code"] == code and done["state"] == "failed", done
        assert client.acts == 0
        assert client.checks == (5 if code in browser.RETRYABLE else 1)
        assert done["effects"][step.id]["state"] == "not_dispatched"
    finally:
        engine.close()


def test_a_blocked_click_can_be_asked_for_again(tmp_path):
    engine, _, _ = click(tmp_path, FakeMcp([COVERED]))
    engine.close()
    client = FakeMcp([GOOD])
    engine, _, done = click(tmp_path, client)           # same action, same ledger
    engine.close()
    assert done["state"] == "completed" and client.acts == 1


def test_settles_then_dispatches_exactly_once(tmp_path):
    client = FakeMcp([MOVING, MOVING, GOOD])
    engine, _, done = click(tmp_path, client)
    engine.close()
    assert done["state"] == "completed", done
    assert (client.checks, client.acts) == (3, 1)


def test_a_failed_dispatch_is_never_retried(tmp_path):
    client = FakeMcp([GOOD], act_error=ExecutionError("BROWSER_DISCONNECTED", "lost"))
    engine, step, done = click(tmp_path, client)
    try:
        assert client.acts == 1 and done["state"] == "unknown"
        assert done["effects"][step.id]["state"] == "unknown"
        assert any(e["payload"].get("reason") == "dispatch_boundary_interrupted_no_retry" for e in done["events"])
    finally:
        engine.close()
