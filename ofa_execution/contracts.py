"""Public contracts. Future voice/model adapters submit these same structures."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def uid() -> str:
    return str(uuid4())


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode()).hexdigest()


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


Operation = Literal["app.open", "window.observe", "window.focus", "window.minimize", "window.maximize", "window.restore", "window.close", "desktop.click",
                    "desktop.fill", "desktop.type", "desktop.scroll", "desktop.screenshot",
                    "browser.open", "browser.observe", "browser.click", "browser.fill",
                    "browser.scroll", "browser.screenshot", "browser.close",
                    "file.read", "file.write", "website.open", "slack.send_file"]


class Target(Contract):
    app: str | None = None
    tab: str | None = None
    name: str | None = None
    role: str | None = None
    ref: str | None = None
    path: str | None = None
    destination: str | None = None


class Expectation(Contract):
    kind: Literal["changed", "value", "text", "url", "file_text"] = "changed"
    value: str | None = Field(default=None, max_length=16384)


class Step(Contract):
    id: str = Field(default_factory=uid, min_length=1, max_length=100)
    operation: Operation
    target: Target = Field(default_factory=Target)
    text: str | None = Field(default=None, max_length=16384)
    url: str | None = Field(default=None, max_length=2048)
    direction: Literal["up", "down"] = "down"
    expect: Expectation | None = None


class Plan(Contract):
    schema_version: Literal["ofa.execution.v1"] = "ofa.execution.v1"
    title: str = Field(min_length=1, max_length=200)
    steps: list[Step] = Field(min_length=1, max_length=50)
    allowed_origins: list[str] = Field(default_factory=list, max_length=20)
    source: Literal["structured", "deterministic", "mock_planner", "future_planner"] = "structured"

    @model_validator(mode="after")
    def unique_steps(self):
        if len({s.id for s in self.steps}) != len(self.steps):
            raise ValueError("step ids must be unique")
        return self


class Command(Contract):
    command_id: str = Field(default_factory=uid, min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=4096)
    # Future final transcripts map to text with source='voice'; no audio accepted.
    source: Literal["typed", "voice"] = "typed"


class Submission(Contract):
    command_id: str = Field(default_factory=uid, min_length=1, max_length=100)
    plan: Plan


class Decision(Contract):
    command_id: str = Field(default_factory=uid, min_length=1, max_length=100)
    approval_id: str
    reading_hash: str
    approve: bool


class Answer(Contract):
    command_id: str = Field(default_factory=uid, min_length=1, max_length=100)
    question_id: str
    option_id: str


class Control(Contract):
    command_id: str = Field(default_factory=uid, min_length=1, max_length=100)
    action: Literal["pause", "resume", "cancel", "stop", "continue"]
    handoff_id: str | None = None
    # Future speech-start maps to pause immediately, without waiting for STT.


class Element(Contract):
    ref: str
    name: str = ""
    role: str = ""
    value: str | None = None
    protected: bool = False
    enabled: bool = True
    bounds: list[int] | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Observation(Contract):
    id: str = Field(default_factory=uid)
    surface: str
    identity: dict[str, Any]
    elements: list[Element] = Field(default_factory=list)
    complete: bool = True
    frame: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)

    def semantic(self) -> dict:
        body = self.model_dump(exclude={"id", "frame"})
        # Re-read generates new opaque refs; semantic identity must remain stable.
        for element in body["elements"]:
            element.pop("ref", None)
        return body

    @property
    def hash(self) -> str:
        return digest(self.semantic())


class Evidence(Contract):
    tier: Literal["A", "B", "C", "D"]
    kind: str
    reading_hash: str
    detail: dict[str, Any] = Field(default_factory=dict)


class Outcome(Contract):
    status: Literal["verified", "unknown", "handoff"]
    observation: Observation
    evidence: list[Evidence] = Field(default_factory=list)


class ExecutionError(Exception):
    def __init__(self, code: str, message: str, options: list[dict] | None = None):
        super().__init__(message)
        self.code, self.message, self.options = code, message, options or []


class PlannerAdapter(Protocol):
    """Future provider authenticates elsewhere; returns a plan, never tool access."""
    def plan(self, command: Command, capabilities: dict) -> Plan: ...


class Hand(Protocol):
    def capabilities(self) -> dict: ...
    def observe(self, step: Step) -> Observation: ...
    def execute(self, step: Step, before: Observation, checkpoint) -> Outcome: ...
