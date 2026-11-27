"""Every question OFA asks the user is a LangGraph interrupt().

A node that asks keeps everything before ask() free of side effects: on resume LangGraph re-runs the node
from its start, and ask() then returns the user's answer instead of pausing again.
"""
from __future__ import annotations

from dataclasses import asdict

from langgraph.types import interrupt

from ..policy.approval import Heard
from .state import Answer, Question


def ask(kind: str, say: str, timeout: float, mode: str = "command") -> Answer:
    """Pause the graph; the voice front end speaks `say`, listens, and resumes with an Answer."""
    return interrupt(Question(kind=kind, say=say, timeout=timeout, mode=mode)) or {}


def heard_of(answer: Answer | None) -> Heard | None:
    data = (answer or {}).get("heard")
    return Heard(**data) if data else None


def heard_dict(heard: Heard | None) -> dict | None:
    return asdict(heard) if heard is not None else None
