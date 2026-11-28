"""A restart must not forget what was already sent."""
import pytest

from ofa_execution.config import LocalConfig
from ofa_execution.contracts import (Decision, Evidence, ExecutionError, Expectation, Observation,
                                     Outcome, Plan, Step, Target, uid)
from ofa_execution.engine import Engine
from ofa_execution.ledger import default_dir
from ofa_execution.planner import DeterministicPlanner

from tests.local_execution.test_core import approve, wait

DONE = {"completed", "failed", "unknown", "cancelled"}
SECRET = "canary-value-9f3b-never-on-disk"


class Sender:
    """A hand whose dispatch can be made to crash after sending."""
    def __init__(self, crash=False):
        self.crash, self.sent = crash, 0

    def capabilities(self):
        return {}

    def observe(self, step):
        return Observation(surface="file", identity={"path": step.target.path})

    def execute(self, step, before, checkpoint):
        self.sent += 1
        if self.crash:
            raise RuntimeError("process died after dispatch")
        return Outcome(status="verified", observation=before,
                       evidence=[Evidence(tier="A", kind="file_readback", reading_hash=before.hash)])


def start(tmp_path, hand):
    config = LocalConfig(write_roots=[str(tmp_path)], ledger_dir=str(tmp_path / "ledger"))
    return Engine(config, {"files": hand}, DeterministicPlanner(config))


def plan(tmp_path, step_id="send-1", text=SECRET):
    return Plan(title="send", steps=[Step(id=step_id, operation="file.write", text=text,
                                          target=Target(path=str(tmp_path / "a.txt")),
                                          expect=Expectation(kind="file_text", value=text))])


def run(engine, submitted):
    task = engine.submit(uid(), submitted)["task_id"]
    snap = wait(engine, task, {"approval"} | DONE)
    if snap["state"] == "approval":
        approve(engine, task, snap)
        snap = wait(engine, task, DONE)
    return snap


@pytest.mark.parametrize("step_id", ["send-1", "send-again"])
def test_unknown_outcome_survives_restart(tmp_path, step_id):
    first = start(tmp_path, Sender(crash=True))
    assert run(first, plan(tmp_path))["state"] == "unknown"
    first.close()
    hand = Sender()
    second = start(tmp_path, hand)
    try:
        snap = run(second, plan(tmp_path, step_id))
        assert snap["state"] == "unknown" and snap["error"]["code"] == "OUTCOME_UNKNOWN"
        assert snap["approval"] is None and hand.sent == 0
    finally:
        second.close()


def test_verified_step_is_not_replayed_but_a_new_step_is_allowed(tmp_path):
    first = start(tmp_path, Sender())
    assert run(first, plan(tmp_path))["state"] == "completed"
    first.close()
    hand = Sender()
    second = start(tmp_path, hand)
    try:
        assert run(second, plan(tmp_path))["error"]["code"] == "ALREADY_DONE"
        assert hand.sent == 0
        assert run(second, plan(tmp_path, "a-new-request"))["state"] == "completed"
        assert hand.sent == 1
    finally:
        second.close()


def test_old_command_and_approval_cannot_be_reused(tmp_path):
    first = start(tmp_path, Sender())
    command = uid()
    submitted = plan(tmp_path)
    old = first.submit(command, submitted)
    snap = wait(first, old["task_id"], {"approval"})
    approve(first, old["task_id"], snap)
    wait(first, old["task_id"], DONE)
    first.close()
    hand = Sender()
    second = start(tmp_path, hand)
    try:
        assert second.submit(command, submitted) == old
        assert not second.tasks and hand.sent == 0
        card = snap["approval"]
        with pytest.raises(ExecutionError) as error:
            second.decide(old["task_id"], Decision(approval_id=card["id"],
                                                   reading_hash=card["reading_hash"], approve=True))
        assert error.value.code == "TASK_NOT_FOUND"
        assert {"commit_authorised", "completed"} <= {e["type"] for e in second.ledger.events}
    finally:
        second.close()


def test_nothing_private_is_written(tmp_path):
    engine = start(tmp_path, Sender())
    run(engine, plan(tmp_path))
    engine.close()
    written = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "ledger").glob("*.jsonl"))
    assert "commit_authorised" in written
    assert SECRET not in written and "a.txt" not in written


def test_half_written_line_is_dropped_and_damage_fails_closed(tmp_path):
    first = start(tmp_path, Sender(crash=True))
    run(first, plan(tmp_path))
    first.close()
    log = next((tmp_path / "ledger").glob("*.jsonl"))
    with log.open("ab") as stream:
        stream.write(b'{"record": "eff')
    second = start(tmp_path, Sender())
    assert run(second, plan(tmp_path))["error"]["code"] == "OUTCOME_UNKNOWN"
    second.close()
    log.write_bytes(b"not json\n" + log.read_bytes())
    with pytest.raises(ExecutionError) as error:
        start(tmp_path, Sender())
    assert error.value.code == "LEDGER_CORRUPT"


def test_unwritable_ledger_blocks_dispatch(tmp_path, monkeypatch):
    hand = Sender()
    engine = start(tmp_path, hand)
    try:
        task = engine.submit(uid(), plan(tmp_path))["task_id"]
        snap = wait(engine, task, {"approval"})

        def broken(*args, **kwargs):
            raise ExecutionError("LEDGER_UNAVAILABLE", "disk full")
        monkeypatch.setattr(engine.ledger, "effect", broken)
        approve(engine, task, snap)
        done = wait(engine, task, DONE)
        assert done["error"]["code"] == "LEDGER_UNAVAILABLE" and hand.sent == 0
    finally:
        engine.close()


def test_launcher_default_can_be_switched_off(tmp_path):
    assert default_dir("local", "off") is None
    assert default_dir("local", str(tmp_path)) == str(tmp_path)
    assert default_dir("voice").endswith("voice")
