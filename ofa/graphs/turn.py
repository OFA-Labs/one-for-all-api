"""Turn graph: one finished utterance in, one spoken result out.

    route ─┬─(pause / continue)─▶ control ─▶ END
           └─(anything else)────▶ brain[subgraph] ─▶ END

The companion's own instant "open <app>" path and Caps Lock / "stop" are handled by voice/session.py before
a sentence reaches this graph; while a task is running, "pause" is applied there too, because the task's
thread is busy.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from ..speech.controls import control_of
from .brain import brain_graph
from .deps import Deps
from .report import TurnResult
from .state import TurnState


def turn_graph(deps: Deps) -> StateGraph:
    def route(s: TurnState) -> dict:
        kind = control_of(s["text"])
        if kind in {"pause", "resume"} and deps.control is not None:
            return {"route": "control"}
        return {"route": "brain"}

    def control(s: TurnState) -> dict:
        reply = deps.control(control_of(s["text"])) or "Okay."
        return {"result": TurnResult(reply, "answered").as_state()}

    g = StateGraph(TurnState)
    g.add_node("route", route)
    g.add_node("control", control)
    g.add_node("brain", brain_graph(deps).compile())
    g.add_edge(START, "route")
    g.add_conditional_edges("route", lambda s: s["route"], ["control", "brain"])
    g.add_edge("control", END)
    g.add_edge("brain", END)
    return g
