"""Hands subgraph: the only path from a tool call to the desktop, files, shell and credential broker (§6, §10.1).

    hold ─▶ prepare ─┬─▶ classify ─┬─(tier 0/1)──────────────────────────────▶ effect ─▶ END
                     │             └─(tier 2)─▶ approve[subgraph] ─▶ approved ─┘
                     ├─▶ dictation ─(no words yet)─▶ dictation_listen ─(unsure)─▶ dictation_confirm
                     │        └──────────────▶ dictation_ready ─▶ classify
                     └─(propose_plan)─▶ approve ─▶ approved (records the plan) ─▶ END

Rules stay in plain modules this graph calls: ofa.policy (tiers, approvals), ofa.dictation (verbatim),
ofa.action_context (what OFA itself read on screen), ofa.effects (what an authorised action does).
Every node that pauses does nothing before ask(); every effect runs in its own node after approval, so
resuming a saved task never repeats an action.
"""
from __future__ import annotations

import asyncio
import re
import time

from langgraph.graph import END, START, StateGraph

from ..action_context import describe
from ..dictation import paraphrases_dictation
from ..effects import run_effect
from ..harness.api import HarnessError
from ..policy import Action, PolicyDenied, classify, classify_tier
from ..text.dictation import find_span, verbatim
from ..text.translit import apply_script
from ..tools import ToolArgError, parse_args, to_action
from .approval import approval_graph
from .deps import Deps
from .pauses import ask, heard_of
from .state import HandsState, jsonable

OUTBOUND = {"send", "post", "forward", "share", "publish", "submit", "apply", "upload", "attach", "comment",
            "approve", "push", "merge", "pay", "purchase", "book", "order", "phone_send"}
READS = {"screen", "windows", "wait_for", "read_file", "files", "look"}
EFFECT_TIMEOUT, GLANCE_TIMEOUT = 90.0, 15.0     # longer than the slowest effect (a 60 s command)
GLANCE_AFTER = {"open", "click", "double_click", "right_click", "key", "focus", "type", "replace", "dictate",
                "scroll_up", "scroll_down", "close"}


def _done(out: dict, action: Action | None = None, name: str = "", tier: int = 2) -> dict:
    """Finish the subgraph with a result for the engine (and a record for the report when an action ran)."""
    out = jsonable({**out, "tier": out.get("tier", tier)})
    info = None
    if action is not None:
        info = {"tool": name, "verb": action.verb, "status": out.get("status"), "tier": out["tier"],
                "verified": bool(out.get("verified")), "outcome": out.get("outcome")}
    return {"tool_out": out, "action_info": info, "route": "end"}


def hands_graph(deps: Deps) -> StateGraph:
    def on_popup(action: Action) -> bool:
        """Is this click aimed at the pop-up that just appeared (an incoming call)?"""
        popup = deps.attention.latest()
        if not popup:
            return False
        l, t, r, b = popup["rect"]
        if action.args.get("x") is not None:
            return l <= action.args["x"] < r and t <= action.args["y"] < b
        try:
            el = deps.harness.element(action.args.get("element") or "")
        except HarnessError:
            return False
        x, y = el.center()
        return el.hwnd == popup["hwnd"] or (l <= x < r and t <= y < b)

    async def hold(s: HandsState) -> dict:
        await deps.voice.pause_gate()            # spoken "pause" holds here; "stop" changes the epoch
        return {"hands_epoch": deps.epoch(), "tool_out": None, "action_info": None}

    def prepare(s: HandsState) -> dict:
        call = s["call"]
        try:
            args = parse_args(call["args_json"])
        except ToolArgError as exc:
            return _done({"status": "error", "reason": "BAD_ARGS", "detail": str(exc)})
        if call["name"] == "propose_plan":
            steps = [str(x)[:200] for x in (args.get("steps") or [])][:12]
            if not steps:
                return _done({"status": "error", "reason": "EMPTY_PLAN"})
            text = "Here is my plan. " + " ".join(f"{i + 1}. {x.rstrip('.')}." for i, x in enumerate(steps))
            plan = Action(verb="plan", payload="\n".join(steps), args={"op": "plan"})
            return {"action": plan.model_dump(), "spoken": text + " Should I go ahead?", "route": "approve"}
        try:
            action = to_action(call["name"], args, s["turn_id"])
        except ToolArgError as exc:
            return _done({"status": "error", "reason": "BAD_ARGS", "detail": str(exc)})
        deps.show("acting")
        hands = deps.settings.get().hands
        if action.args.get("op") == "system" and not hands.system_controls:
            return _done({"status": "refused", "reason": "SYSTEM_CONTROLS_OFF",
                          "detail": "System controls are turned off in Settings → Hands."}, action, call["name"])
        action = describe(deps.harness, action)
        if hands.answer_calls and action.verb == "click" and on_popup(action):
            action = action.model_copy(update={"context": "incoming_call"})
        if paraphrases_dictation(action, s["text"]):
            return _done({"status": "rejected", "reason": "VERBATIM_MISMATCH",
                          "detail": "The user dictated: type their exact words (use dictate), or mode=compose "
                                    "only if they asked you to write it."}, action, call["name"])
        route = "dictation" if action.verb == "dictate" else "classify"
        return {"action": action.model_dump(), "spoken": None, "route": route}

    # --- dictation (C4): the user's exact words, or a draft they asked for -------------------------------
    def dictation(s: HandsState) -> dict:
        action = Action.model_validate(s["action"])
        text = action.payload or ""
        if action.args.get("mode", "verbatim") != "verbatim":
            return {"dictation": {"text": text}, "route": "dictation_ready"}
        span = find_span(s["text"], text) if text else None
        if text and span is None:
            return _done({"status": "rejected", "reason": "VERBATIM_MISMATCH",
                          "detail": "text must be copied exactly from the user's words; omit text to ask the user "
                                    "to dictate"}, action, s["call"]["name"])
        if span is None:
            return {"route": "dictation_listen"}
        return {"dictation": {"span": span}, "route": "dictation_ready"}

    def dictation_listen(s: HandsState) -> dict:
        heard = heard_of(ask("dictation", "What should I type?", 45.0, mode="dictation"))
        if heard is None or not heard.text.strip():
            return _done({"status": "error", "reason": "NO_DICTATION"}, Action.model_validate(s["action"]),
                         s["call"]["name"])
        unsure = heard.confidence is not None and heard.confidence < 0.85 and re.search(r"\d|[A-Z][a-z]+", heard.text)
        return {"dictation": {"span": heard.text}, "route": "dictation_confirm" if unsure else "dictation_ready"}

    def dictation_confirm(s: HandsState) -> dict:
        span = s["dictation"]["span"]
        heard = heard_of(ask("confirm", f"I heard: {span}. Is that right?", 8.0))
        if heard is None or classify(heard.text) != "YES":
            return _done({"status": "error", "reason": "DICTATION_NOT_CONFIRMED"}, Action.model_validate(s["action"]),
                         s["call"]["name"])
        return {"route": "dictation_ready"}

    async def dictation_ready(s: HandsState) -> dict:
        action = Action.model_validate(s["action"])
        d = s["dictation"]
        text = verbatim(apply_script(d["span"], deps.memory.get("script", "roman"))) if "span" in d else d["text"]
        if not text.strip():
            return _done({"status": "error", "reason": "NOTHING_TO_TYPE"}, action, s["call"]["name"])
        await deps.voice.speak("Typing it now.")
        return {"action": action.model_copy(update={"payload": text}).model_dump(), "route": "classify"}

    # --- the gate -----------------------------------------------------------------------------------
    def classify_node(s: HandsState) -> dict:
        action = Action.model_validate(s["action"])
        tier = classify_tier(action, deps.turns, s["hands_epoch"])
        effectful = tier >= 1 and action.args.get("op") not in READS
        effects = s.get("effects_this_turn", 0) + int(effectful)
        update = {"tier": tier, "effects_this_turn": effects}
        if tier < 2:
            return {**update, "route": "effect"}
        tier2 = s.get("tier2_this_turn", 0) + 1
        update["tier2_this_turn"] = tier2
        name = s["call"]["name"]
        if s.get("plan_approved") is None and (tier2 >= 2 or effects >= 5):
            return {**update, **_done({"status": "blocked", "reason": "PLAN_REQUIRED",
                                       "detail": "This is a multi-step consequential task: call propose_plan first."},
                                      action, name)}
        prior = deps.memory.ledger_get(action.digest())
        if action.verb in OUTBOUND and prior == "done":
            return {**update, **_done({"status": "skipped", "reason": "ALREADY_DONE",
                                       "detail": "This exact action already succeeded; not repeating it."}, action, name)}
        if action.verb in OUTBOUND and prior in {"unknown", "intent"}:
            return {**update, **_done({"status": "blocked", "reason": "OUTCOME_UNKNOWN",
                                       "detail": "A previous identical attempt has an unknown outcome. Check the "
                                                 "destination first, or ask the user."}, action, name)}
        deps.show("approval", action)
        return {**update, "route": "approve"}

    def approved(s: HandsState) -> dict:
        action = Action.model_validate(s["action"])
        verdict, plan = s["verdict"], action.verb == "plan"
        if plan:
            deps.audit.write("plan", epoch=s["hands_epoch"], task=s["task"], digest=action.digest(), result=verdict)
        else:
            deps.audit.write("approval", epoch=s["hands_epoch"], task=s["task"], tier=2, digest=action.digest(),
                             result=verdict, handle_ids=[action.handle] if action.handle else [])
            deps.show("approval_done", None)
        if verdict != "granted":
            out = {"status": verdict if plan else "not_approved", **({} if plan else {"state": verdict})}
            if s.get("verdict_text") and (plan or verdict == "modify"):
                out["user_said"] = s["verdict_text"]
            return _done(out, None if plan else action, s["call"]["name"])
        try:
            deps.approvals.consume(s["approval_id"], action, deps.epoch())
        except PolicyDenied as exc:
            return _done({"status": "refused", "reason": exc.code}, None if plan else action, s["call"]["name"])
        if plan:
            return {"plan_approved": action.digest(), **_done(
                {"status": "approved", "note": "Each consequential step will still be confirmed when it happens."})}
        for dest in action.destinations or [action.target or action.verb]:
            deps.memory.ledger_set(s["task"], action.digest(), dest, action.verb, "intent")
        return {"consumed_at": time.time(), "route": "effect"}

    async def effect(s: HandsState) -> dict:
        action = Action.model_validate(s["action"])
        tier, name = s["tier"], s["call"]["name"]
        if deps.epoch() != s["hands_epoch"]:
            return _done({"status": "cancelled", "reason": "SESSION_STOPPED"}, action, name, tier)
        if tier == 2 and time.time() - s.get("consumed_at", 0) > deps.approvals.ttl:
            return _done({"status": "refused", "reason": "APPROVAL_STALE",
                          "detail": "The approval is too old; ask again."}, action, name, tier)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(run_effect, deps.harness, deps.memory, deps.broker, action), EFFECT_TIMEOUT)
        except asyncio.TimeoutError:      # the outcome is unknown: say so, and never retry it blindly
            result = {"status": "error", "reason": "TIMEOUT",
                      "detail": "The action did not return in time; check the screen before doing anything else."}
        except HarnessError as exc:
            result = {"status": "error", "reason": exc.code, "detail": str(exc), "options": exc.options}
        except PolicyDenied as exc:
            result = {"status": "refused", "reason": exc.code}
        except PermissionError as exc:
            result = {"status": "handoff", "reason": "INPUT_BLOCKED", "detail": str(exc)}
        except Exception as exc:   # report honestly; never claim success
            result = {"status": "error", "reason": type(exc).__name__, "detail": str(exc)[:200]}
        result.setdefault("status", "ok")
        if action.args.get("op") in GLANCE_AFTER and result["status"] != "cancelled":
            try:
                glance = await asyncio.wait_for(asyncio.to_thread(deps.harness.glance), GLANCE_TIMEOUT)
            except asyncio.TimeoutError:
                glance = None
            if glance:
                result["now"] = glance
        if tier == 2:
            verified = result["status"] == "ok" and result.get("verified", result.get("screen_changed", False))
            failed = result["status"] in {"error", "refused"} and result.get("reason") != "TIMEOUT"
            outcome = "done" if verified else ("failed" if failed else "unknown")
            for dest in action.destinations or [action.target or action.verb]:
                deps.memory.ledger_set(s["task"], action.digest(), dest, action.verb, outcome)
            result["outcome"] = outcome
        deps.audit.write("action", epoch=s["hands_epoch"], task=s["task"], tier=tier, digest=action.digest(),
                         result=result["status"], detail=action.verb, handle_ids=[action.handle] if action.handle else [])
        return _done(result, action, name, tier)

    g = StateGraph(HandsState)
    for node in (hold, prepare, dictation, dictation_listen, dictation_confirm, dictation_ready, approved, effect):
        g.add_node(node.__name__, node)
    g.add_node("classify", classify_node)
    g.add_node("approve", approval_graph(deps.approvals, deps.lang).compile())
    g.add_edge(START, "hold")
    g.add_edge("hold", "prepare")
    by_route = lambda s: END if s.get("route") == "end" else s["route"]
    g.add_conditional_edges("prepare", by_route, ["classify", "dictation", "approve", END])
    g.add_conditional_edges("dictation", by_route, ["dictation_listen", "dictation_ready", END])
    g.add_conditional_edges("dictation_listen", by_route, ["dictation_confirm", "dictation_ready", END])
    g.add_conditional_edges("dictation_confirm", by_route, ["dictation_ready", END])
    g.add_conditional_edges("dictation_ready", by_route, ["classify", END])
    g.add_conditional_edges("classify", by_route, ["effect", "approve", END])
    g.add_edge("approve", "approved")
    g.add_conditional_edges("approved", by_route, ["effect", END])
    g.add_edge("effect", END)
    return g
