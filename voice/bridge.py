"""Reuse the existing executor and require evidence before success speech."""
from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from ofa_execution.contracts import Control, Plan, Step, Target, Decision, Answer

from .contracts import ProviderError
from .websites import validate_url


class EngineBridge:
    def __init__(self, engine: Any, sites: Mapping[str, str] | None = None, emit=lambda *_: None) -> None:
        self.engine = engine
        self.sites = dict(sites or {})
        self._active: set[str] = set()
        self.emit = emit
        self.pending: dict | None = None
        self.last_snapshot: dict = {}

    async def execute(self, step: Step, command_id: str) -> dict:
        parsed=urlsplit(step.url or "")
        plan = Plan(title=step.operation, steps=[step], source="deterministic",
                    allowed_origins=[f"{parsed.scheme}://{parsed.netloc}"] if step.operation=="browser.open" else [])
        return await self._submit(plan, command_id)

    async def _submit(self, plan, command_id):
        submission = asyncio.create_task(asyncio.to_thread(self.engine.submit, command_id, plan))
        try:
            result = await asyncio.shield(submission)
        except asyncio.CancelledError:
            self.engine.emergency_stop()
            result = await submission
            self.engine.control(result["task_id"], Control(action="cancel"))
            raise
        task_id = result["task_id"]
        self._active.add(task_id)
        try:
            await self._wait(task_id, None)
            return self.last_snapshot
        except asyncio.CancelledError:
            self.engine.control(task_id, Control(action="cancel"))
            raise
        finally:
            self._active.discard(task_id)
            if self.pending and self.pending["task_id"] == task_id:
                self.pending = None
                self.emit("task_update", {"task_id":task_id,"state":"cleared"})

    def decide(self, task_id, decision):
        if task_id not in self._active:
            raise PermissionError("This task is no longer active")
        return self.engine.decide(task_id, Decision.model_validate(decision))

    def answer(self, task_id, answer):
        if task_id not in self._active:
            raise PermissionError("This task is no longer active")
        return self.engine.answer(task_id, Answer.model_validate(answer))

    def continue_task(self, task_id, handoff_id):
        if task_id not in self._active:
            raise PermissionError("This task is no longer active")
        return self.engine.control(task_id, Control(action="continue",handoff_id=handoff_id))

    async def open(self, name: str, command_id: str) -> bool:
        url = self.sites.get(name)
        parsed = urlsplit(url) if url else None
        step = (Step(id=command_id + ":open", operation="browser.open", url=url) if url
                else Step(id=command_id + ":open", operation="app.open", target=Target(app=name)))
        plan = Plan(title=("Open " + name)[:200], steps=[step], source="deterministic",
                    allowed_origins=[f"{parsed.scheme}://{parsed.netloc}"] if parsed else [])
        evidence_kind = "fresh_tab_url" if url else "process_and_window_readback"
        submission = asyncio.create_task(asyncio.to_thread(self.engine.submit, command_id, plan))
        try:
            result = await asyncio.shield(submission)
        except asyncio.CancelledError:
            self.engine.emergency_stop()
            result = await submission
            self.engine.control(result["task_id"], Control(action="cancel"))
            raise
        task_id = result["task_id"]
        self._active.add(task_id)
        try:
            return await self._wait(task_id, evidence_kind)
        except asyncio.CancelledError:
            self.engine.control(task_id, Control(action="cancel"))
            raise
        finally:
            self._active.discard(task_id)

    async def _wait(self, task_id: str, evidence_kind: str | None) -> bool:
        deadline = time.monotonic() + 30
        previous = None
        while time.monotonic() < deadline:
            snapshot = await asyncio.to_thread(
                self.engine.snapshot, task_id
            )
            state = snapshot["state"]
            self.last_snapshot = snapshot
            version = (state, snapshot.get("last_sequence",0))
            if version != previous:
                payload = {"task_id":task_id,"state":state,"approval":snapshot.get("approval"),
                           "question":snapshot.get("question"),"handoff":snapshot.get("handoff"),"error":snapshot.get("error")}
                self.pending = payload if state in {"approval","question","handoff"} else None
                self.emit("task_update",payload)
                previous = version
            if state in {"approval","question","handoff","paused"}:
                deadline = time.monotonic() + 30
            if state == "completed":
                if evidence_kind is None:
                    return True
                return any(
                    event["type"] == "step_verified" and any(
                        evidence["tier"] == "A" and
                        evidence["kind"] == evidence_kind
                        for evidence in event["payload"].get("evidence", [])
                    )
                    for event in snapshot["events"]
                )
            if state in {"dispatched", "failed", "unknown", "cancelled"}:
                return False
            await asyncio.sleep(0.02)
        self.engine.control(task_id, Control(action="cancel"))
        raise ProviderError("LAUNCH_NOT_VERIFIED")

    def stop(self) -> None:
        self.engine.emergency_stop()
        for task_id in tuple(self._active):
            self.engine.control(task_id, Control(action="cancel"))

    def resume(self) -> None:
        self.engine.control(None, Control(action="resume"))

    async def open_url(self, url: str) -> bool:
        """A browser dispatch receipt, deliberately not a page-load verification."""
        from uuid import uuid4
        snapshot = await self.execute(Step(operation="website.open",url=validate_url(url)),str(uuid4()))
        return snapshot["state"] == "dispatched"
