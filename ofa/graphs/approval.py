"""Approval subgraph (§6): one exact action, a spoken yes, nothing else.

    open ──▶ listen ──(pending)──▶ listen …
                     └─(granted | denied | modify | expired | invalidated)──▶ END

The rules live in ofa.policy (ApprovalStore.ask / decide / expire, the yes-no lexicon). This graph only
orders them: it speaks the request, waits for the user's words through interrupt(), and re-asks once.
Only microphone speech that is not OFA's own voice, heard after OFA stopped speaking, can grant.
"""
from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph

from ..policy import Action, ApprovalState, ApprovalStore, PolicyDenied
from .pauses import ask, heard_of
from .state import ApprovalFlow


def approval_graph(approvals: ApprovalStore, lang=lambda: "en") -> StateGraph:
    """The builder; a parent graph compiles it as a subgraph, obtain() compiles it on its own."""
    def open_request(s: ApprovalFlow) -> dict:
        action = Action.model_validate(s["action"])
        try:
            req = approvals.ask(action, lang(), s.get("spoken"))
        except PolicyDenied as exc:
            return {"verdict": "refused", "verdict_text": exc.code, "approval_id": ""}
        reask = "Haan ya nahi boliye." if lang() == "hi" else "Should I go ahead? Please say yes or no."
        return {"approval_id": req.id, "verdict": ApprovalState.PENDING.value,
                "approval": {"id": req.id, "prompts": [req.spoken, reask], "attempt": 0, "say": req.spoken,
                             "deadline": 0.0, "tts_end": 0.0}}

    def listen(s: ApprovalFlow) -> dict:
        a = dict(s["approval"])
        timeout = approvals.window if a["say"] else max(0.1, a["deadline"] - time.monotonic())
        answer = ask("approval", a["say"], timeout)
        # ---- below runs once, after the user's answer arrives ----
        if a["say"]:                                   # a fresh prompt opens a fresh listening window
            a["tts_end"] = answer.get("tts_end", time.monotonic())
            a["deadline"] = answer.get("listen_started", time.monotonic()) + approvals.window
        heard = heard_of(answer)
        state = approvals.decide(a["id"], heard, a["tts_end"]) if heard else ApprovalState.PENDING
        if state != ApprovalState.PENDING:
            return {"approval": a, "verdict": state.value, "verdict_text": approvals.get(a["id"]).transcript}
        if heard is not None and a["deadline"] - time.monotonic() > 0.1:
            a["say"] = ""                              # unclear or not admissible: keep listening
        else:
            a["attempt"] += 1
            if a["attempt"] >= len(a["prompts"]):
                approvals.expire(a["id"])
                return {"approval": a, "verdict": ApprovalState.EXPIRED.value}
            a["say"] = a["prompts"][a["attempt"]]
        return {"approval": a, "verdict": ApprovalState.PENDING.value}

    g = StateGraph(ApprovalFlow)
    g.add_node("open", open_request)
    g.add_node("listen", listen)
    g.add_edge(START, "open")
    g.add_conditional_edges("open", lambda s: "listen" if s["verdict"] == "pending" else END, ["listen", END])
    g.add_conditional_edges("listen", lambda s: "listen" if s["verdict"] == "pending" else END, ["listen", END])
    return g


async def obtain(approvals: ApprovalStore, action: Action, speak, listen, lang: str = "en",
                 spoken: str | None = None):
    """Run the approval subgraph on its own (tests, typed tools). Returns the ApprovalRequest."""
    from langgraph.checkpoint.memory import InMemorySaver

    from .runner import CallbackIO, drive
    graph = approval_graph(approvals, lambda: lang).compile(checkpointer=InMemorySaver())
    out = await drive(graph, {"action": action.model_dump(), "spoken": spoken},
                      {"configurable": {"thread_id": action.id}}, CallbackIO(speak, listen))
    if not out.get("approval_id"):
        raise PolicyDenied(out.get("verdict_text") or "NO_APPROVAL")
    return approvals.get(out["approval_id"])
