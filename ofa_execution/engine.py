"""Serial local orchestrator, one gate, bounded volatile state and event log."""
from __future__ import annotations

import copy
import threading
import time
from collections import deque
from dataclasses import dataclass, field

from .contracts import ExecutionError, Plan, digest, uid
from .policy import Gate


TERMINAL = {"completed", "failed", "cancelled", "unknown"}


@dataclass
class Task:
    id: str
    plan: Plan
    state: str = "queued"
    step: int = 0
    epoch: int = 0
    held: bool = False
    cancelled: bool = False
    approval: dict | None = None
    question: dict | None = None
    handoff: dict | None = None
    observation: dict | None = None
    error: dict | None = None
    effects: dict = field(default_factory=dict)
    events: deque = field(default_factory=lambda: deque(maxlen=500))
    sequence: int = 0


class Engine:
    def __init__(self, config, hands, planner):
        self.config, self.hands, self.planner = config, hands, planner
        self.gate = Gate(config)
        self.session_id = uid()
        self.tasks: dict[str, Task] = {}
        self._commands: dict[str, tuple[str, object]] = {}
        self._cv = threading.Condition(threading.RLock())
        self._stopped = False
        self._closed = False
        self.runtime_capabilities = {}
        self._thread = threading.Thread(target=self._work, name="ofa-local-executor", daemon=True)
        self._thread.start()

    def capabilities(self):
        return {"schema_version": "ofa.execution.v1", "session_id": self.session_id,
                "planner": "deterministic_only", "voice": "future_integration",
                "hands": {k: h.capabilities() for k, h in self.hands.items()},
                "apps": [a.name for a in self.config.apps], "queue_limit": 3,
                "history": "bounded_in_memory", "stopped": self._stopped,
                "local_controls": self.runtime_capabilities}

    def _event(self, task, kind, **payload):
        task.sequence += 1
        task.events.append({"sequence": task.sequence, "event_id": uid(), "task_id": task.id,
                            "step_id": task.plan.steps[task.step].id if task.step < len(task.plan.steps) else None,
                            "attempt": 1, "session_id": self.session_id, "hand_id": self._hand_key(task.plan.steps[min(task.step, len(task.plan.steps)-1)]),
                            "approval_id": task.approval["id"] if task.approval else None,
                            "timestamp": time.time(), "type": kind, "payload": payload})
        self._cv.notify_all()

    @staticmethod
    def _hand_key(step):
        return next((key for prefix, key in (("browser.", "browser"), ("file.", "files"),
                    ("website.", "websites"), ("slack.", "slack")) if step.operation.startswith(prefix)), "desktop")

    def _once(self, command_id, payload, fn):
        with self._cv:
            hashed = digest(payload)
            if command_id in self._commands:
                old_hash, result = self._commands[command_id]
                if old_hash != hashed:
                    raise ExecutionError("COMMAND_ID_CONFLICT", "This command ID was used for a different request.")
                return copy.deepcopy(result)
            if len(self._commands) >= 1000:
                raise ExecutionError("SESSION_LIMIT", "Restart the local session after checking pending work.")
            result = fn()
            self._commands[command_id] = (hashed, copy.deepcopy(result))
            return result

    def _create_task(self, plan: Plan):
        # Called inside _once's scheduling lock. Planning happens outside it so
        # future provider latency cannot block pause or the emergency stop.
        if self._stopped:
            raise ExecutionError("STOPPED", "Emergency stop is active. Explicitly resume local control first.")
        live = [t for t in self.tasks.values() if t.state not in TERMINAL]
        if len(live) >= 4:
            raise ExecutionError("QUEUE_FULL", "One foreground and three queued tasks are supported.")
        if len(self.tasks) >= self.config.max_tasks:
            oldest = next((key for key, value in self.tasks.items() if value.state in TERMINAL), None)
            if oldest is None:
                raise ExecutionError("SESSION_LIMIT", "All bounded task slots are active.")
            del self.tasks[oldest]  # Deduplication tombstones remain; never replay an evicted task.
        frozen = plan.model_copy(deep=True)
        task = Task(uid(), frozen)
        self.tasks[task.id] = task
        self._event(task, "plan_frozen", plan_hash=digest(frozen.model_dump()))
        return {"task_id": task.id, "session_id": self.session_id, "state": "queued"}

    def submit(self, command_id: str, plan: Plan):
        # DNS/application discovery can block. Never hold the control lock while
        # screening a proposed plan; stop is rechecked at the insertion boundary.
        self.gate.screen(plan)
        return self._once(command_id, {"kind": "plan", "plan": plan.model_dump()},
                          lambda: self._create_task(plan))

    def command(self, command):
        plan = self.planner.plan(command, self.capabilities())
        self.gate.screen(plan)
        # Generated step IDs differ on each parse. Deduplicate by the original
        # command input, not those new plan IDs, so a retry returns one task.
        return self._once(command.command_id,
                          {"kind": "command", **command.model_dump(exclude={"command_id"})},
                          lambda: self._create_task(plan))

    def _task(self, task_id):
        if task_id not in self.tasks:
            raise ExecutionError("TASK_NOT_FOUND", "Task is absent from this volatile session; a restart cannot prove an earlier external outcome.")
        return self.tasks[task_id]

    def snapshot(self, task_id):
        with self._cv:
            t = self._task(task_id)
            return copy.deepcopy({"id": t.id, "session_id": self.session_id, "state": t.state,
                                  "step": t.step, "plan": t.plan.model_dump(), "epoch": t.epoch,
                                  "approval": t.approval, "question": t.question, "handoff": t.handoff,
                                  "observation": t.observation, "error": t.error,
                                  "effects": t.effects, "events": list(t.events), "last_sequence": t.sequence})

    def decide(self, task_id, decision):
        def apply():
            t = self._task(task_id)
            card = t.approval
            if not card or card["id"] != decision.approval_id or card["reading_hash"] != decision.reading_hash:
                raise ExecutionError("APPROVAL_STALE", "Approval does not match the currently open card.")
            if card["decision"] is not None:
                raise ExecutionError("ALREADY_DECIDED", "The first approval decision already won.")
            if card["expires_at"] < time.monotonic():
                raise ExecutionError("APPROVAL_EXPIRED", "Request a fresh reading/card.")
            if t.held or self._stopped:
                raise ExecutionError("HELD", "Resume before deciding a rebuilt approval.")
            card["decision"] = decision.approve
            self._event(t, "approval_decided", approve=decision.approve)
            return {"accepted": True}
        return self._once(decision.command_id, {"task": task_id, **decision.model_dump()}, apply)

    def answer(self, task_id, answer):
        def apply():
            t = self._task(task_id)
            q = t.question
            if not q or q["id"] != answer.question_id or q.get("answer") is not None:
                raise ExecutionError("QUESTION_STALE", "The question is no longer open.")
            if answer.option_id not in {o["id"] for o in q["options"]}:
                raise ExecutionError("INVALID_ANSWER", "Choose an offered option.")
            q["answer"] = answer.option_id
            self._event(t, "question_answered")
            return {"accepted": True}
        return self._once(answer.command_id, {"task": task_id, **answer.model_dump()}, apply)

    def control(self, task_id, control):
        def apply():
            tasks = [self._task(task_id)] if task_id else list(self.tasks.values())
            if control.action == "stop":
                self._stopped = True
            elif not task_id and control.action == "resume":
                self._stopped = False
            for t in tasks:
                if t.state in TERMINAL:
                    continue
                if control.action == "continue":
                    if not t.handoff or control.handoff_id != t.handoff["id"]:
                        raise ExecutionError("HANDOFF_STALE", "Explicit Continue must name the current handoff.")
                    t.handoff["continued"] = True
                elif control.action == "cancel":
                    t.cancelled = True
                elif control.action in {"pause", "stop"}:
                    t.held = True
                elif control.action == "resume":
                    if t.handoff:
                        raise ExecutionError("HUMAN_REQUIRED", "Use explicit Continue for the active handoff.")
                    t.held = False
                t.epoch += 1
                self._event(t, control.action, epoch=t.epoch)
            self._cv.notify_all()
            return {"accepted": True, "stopped": self._stopped}
        return self._once(control.command_id, {"task": task_id, **control.model_dump()}, apply)

    def emergency_stop(self):
        # Called directly by global hotkey; does not depend on HTTP or a model.
        from .contracts import Control
        return self.control(None, Control(action="stop"))

    def user_takeover(self):
        """Input activity signal only; never accepts/stores typed key values."""
        with self._cv:
            for t in self.tasks.values():
                if t.state not in TERMINAL and not t.held:
                    t.held = True
                    t.epoch += 1
                    self._event(t, "user_takeover", epoch=t.epoch,
                                held_at_monotonic=time.monotonic())

    def _checkpoint(self, t):
        with self._cv:
            if t.cancelled or self._closed:
                raise ExecutionError("CANCELLED", "Future execution cancelled; existing effects are preserved.")
            if t.held or self._stopped:
                raise ExecutionError("HELD", "Input suppressed by local control.")

    def _wait_active(self, t):
        with self._cv:
            while t.held or self._stopped:
                t.state = "paused"
                if t.cancelled or self._closed:
                    break
                self._cv.wait(0.05)
            self._checkpoint(t)

    def _wait_approval(self, t, step, before):
        with self._cv:
            epoch = t.epoch
            t.approval = {"id": uid(), "step_id": step.id, "operation": step.operation,
                          "reading_hash": before.hash, "reading": before.model_dump(),
                          "exact_action": step.model_dump(), "decision": None,
                          "expires_at": time.monotonic() + self.config.approval_seconds}
            t.state = "approval"
            self._event(t, "approval_opened", reading_hash=before.hash)
            while t.approval["decision"] is None:
                self._checkpoint(t)
                if t.approval["expires_at"] < time.monotonic():
                    raise ExecutionError("APPROVAL_EXPIRED", "Approval expired; no action was sent.")
                self._cv.wait(0.05)
            if not t.approval["decision"]:
                raise ExecutionError("REJECTED", "Action rejected; no effect was dispatched.")
            return epoch

    def _run_step(self, t, step):
        hand = self.hands.get(self._hand_key(step))
        if hand is None:
            raise ExecutionError("HAND_UNAVAILABLE", "This local hand is not configured.")
        while True:
            self._wait_active(t)
            with self._cv:
                t.state = "running"
            before = hand.observe(step)
            if hasattr(hand, "validate_target"):
                hand.validate_target(step, before)
            with self._cv:
                t.observation = before.model_dump()
                self._event(t, "observed", reading_hash=before.hash)
            decision = self.gate.check(step, before)
            if decision == "handoff":
                with self._cv:
                    t.state = "handoff"
                    t.handoff = {"id": uid(), "reason": "human_only_or_unreadable", "continued": False}
                    self._event(t, "handoff")
                    while not t.handoff["continued"]:
                        self._wait_active(t)
                        self._cv.wait(0.05)
                    t.handoff = None
                if hasattr(hand, "after_handoff"):
                    hand.after_handoff(step)
                continue  # Must read and check the surface again, no old command replay.
            token = None
            if decision == "approval":
                try:
                    approved_epoch = self._wait_approval(t, step, before)
                except ExecutionError as exc:
                    if exc.code == "HELD":
                        with self._cv:
                            t.approval = None
                        continue
                    raise
                self._checkpoint(t)
                fresh = hand.observe(step)
                if fresh.hash != before.hash or approved_epoch != t.epoch:
                    with self._cv:
                        self._event(t, "approval_voided", reason="reading_or_control_changed")
                        t.approval = None
                    continue
                before = fresh
                token = self.gate.sign(t.id, step, before, t.epoch)
            try:
                self._checkpoint(t)
            except ExecutionError as exc:
                if exc.code == "HELD":
                    continue
                raise
            with self._cv:
                t.state = "running"
                if token:
                    self.gate.consume(token, t.id, step, before, t.epoch)
                    t.effects[step.id] = {"state": "intent", "reading_hash": before.hash,
                                          "approval_id": t.approval["id"]}
                    self._event(t, "commit_authorised", reading_hash=before.hash)
            try:
                outcome = hand.execute(step, before, lambda: self._checkpoint(t))
            except ExecutionError as exc:
                if token:
                    with self._cv:
                        t.effects[step.id]["state"] = "unknown"
                        self._event(t, "outcome_unknown", reason="dispatch_boundary_interrupted_no_retry")
                elif exc.code == "HELD":
                    continue
                raise
            with self._cv:
                t.observation = outcome.observation.model_dump()
                if outcome.status == "handoff":
                    if token:
                        t.effects[step.id]["state"] = "unknown"
                    t.state = "handoff"
                    t.handoff = {"id": uid(), "reason": outcome.observation.facts.get("reason", "Human assistance required"), "continued": False}
                    t.approval = None
                    self._event(t, "handoff")
                    while not t.handoff["continued"]:
                        self._wait_active(t)
                        self._cv.wait(0.05)
                    t.handoff = None
                    # A close request may have opened a save dialog. Re-observe,
                    # never send another WM_CLOSE when the user continues.
                    if step.operation == "window.close":
                        reading = hand.observe(step)
                        if not reading.facts.get("closed"):
                            raise ExecutionError("HUMAN_REQUIRED", "Close the window yourself before continuing; no second close was sent.")
                        t.observation = reading.model_dump()
                        t.effects[step.id]["state"] = "verified"
                        self._event(t, "step_verified", evidence=[{"tier":"A","kind":"window_closed_readback","reading_hash":reading.hash}])
                        return
                    raise ExecutionError("HUMAN_REQUIRED", "Check the application outcome before a new command.")
                if token:
                    t.effects[step.id]["state"] = "verified" if outcome.status == "verified" else "unknown"
                t.approval = None
                if outcome.status != "verified" or not any(e.tier == "A" for e in outcome.evidence):
                    raise ExecutionError("VERIFICATION_FAILED", "The actual outcome could not be verified; no action will be retried.")
                self._event(t, "step_verified", evidence=[e.model_dump() for e in outcome.evidence])
            return

    def _work(self):
        while not self._closed:
            with self._cv:
                task = next((t for t in self.tasks.values() if t.state == "queued"), None)
                if task is None:
                    self._cv.wait(0.05)
                    continue
                task.state = "running"
            try:
                for index, original in enumerate(task.plan.steps):
                    task.step = index
                    step = original.model_copy(deep=True)
                    try:
                        self._run_step(task, step)
                    except ExecutionError as exc:
                        if exc.options:
                            with self._cv:
                                task.question = {"id": uid(), "code": exc.code, "message": exc.message,
                                                 "options": exc.options, "answer": None}
                                task.state = "question"
                                self._event(task, "question_opened")
                                while task.question["answer"] is None:
                                    self._wait_active(task)
                                    self._cv.wait(0.05)
                                step.target.ref = task.question["answer"]
                                task.question = None
                            self._run_step(task, step)
                        else:
                            raise
                with self._cv:
                    task.state = "completed"
                    self._event(task, "completed")
            except ExecutionError as exc:
                with self._cv:
                    uncertain = any(e["state"] == "unknown" for e in task.effects.values())
                    task.state = "unknown" if uncertain or exc.code == "VERIFICATION_FAILED" else "cancelled" if exc.code == "CANCELLED" else "failed"
                    task.error = {"code": exc.code, "message": exc.message}
                    task.approval = None
                    self._event(task, task.state, **task.error)
            except Exception:
                with self._cv:
                    task.state = "unknown" if task.effects else "failed"
                    task.error = {"code": "HAND_FAILED", "message": "The local hand failed. Check actual application state before a new request."}
                    self._event(task, task.state, **task.error)

    def close(self):
        with self._cv:
            self._closed = True
            self._cv.notify_all()
        self._thread.join(timeout=2)
