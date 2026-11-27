"""Turn graph: one finished utterance in, one spoken result out.

    route ─┬─(pause / continue)──▶ control ─▶ END
           ├─("fill this form")──▶ form_start ─▶ direct_form ─▶ form_report ─▶ END
           └─(anything else)─────▶ brain[subgraph] ─▶ END

The companion's own instant "open <app>" path and Caps Lock / "stop" are handled by voice/session.py before
a sentence reaches this graph; while a task is running, "pause" is applied there too, because the task's
thread is busy.
"""
from __future__ import annotations

import json

from uuid import uuid4

from langgraph.graph import END, START, StateGraph

from ..forms import is_fill_request, named_window
from ..speech.controls import control_of
from .brain import brain_graph
from .deps import Deps
from .form import form_graph
from .report import TurnResult, report
from .state import TurnState


def turn_graph(deps: Deps) -> StateGraph:
    def route(s: TurnState) -> dict:
        kind = control_of(s["text"])
        if kind in {"pause", "resume"} and deps.control is not None:
            return {"route": "control"}
        if is_fill_request(s["text"]):
            return {"route": "form_start"}
        return {"route": "brain"}

    def form_start(s: TurnState) -> dict:
        turn_id = uuid4().hex[:10]
        deps.turns.add(turn_id, s["text"], deps.epoch())
        window = named_window(s["text"], deps.harness.b.list_windows())
        call = {"id": turn_id, "name": "fill_form", "args_json": json.dumps({"window": window} if window else {})}
        return {"call": call, "turn_id": turn_id, "task": turn_id, "plan_approved": None, "effects_this_turn": 0,
                "tier2_this_turn": 0, "finished": None, "action_info": None, "tool_out": None}

    def form_report(s: TurnState) -> dict:
        actions = [s["action_info"]] if s.get("action_info") else []
        result = report(s.get("finished"), [], actions, deps.memory.ledger(s["task"]), deps.lang())
        deps.history[:] = (deps.history + [{"role": "user", "content": s["text"]},
                                           {"role": "assistant", "content": result.spoken}])[-2 * deps.history_turns:]
        return {"result": result.as_state()}

    def control(s: TurnState) -> dict:
        reply = deps.control(control_of(s["text"])) or "Okay."
        return {"result": TurnResult(reply, "answered").as_state()}

    g = StateGraph(TurnState)
    g.add_node("route", route)
    g.add_node("control", control)
    g.add_node("brain", brain_graph(deps).compile())
    g.add_node("form_start", form_start)
    g.add_node("direct_form", form_graph(deps).compile())
    g.add_node("form_report", form_report)
    g.add_edge(START, "route")
    g.add_conditional_edges("route", lambda s: s["route"], ["control", "brain", "form_start"])
    g.add_edge("form_start", "direct_form")
    g.add_edge("direct_form", "form_report")
    g.add_edge("form_report", END)
    g.add_edge("control", END)
    g.add_edge("brain", END)
    return g
