"""The policy gate: classify tier → (Tier 2) spoken approval → consume grant → effect → record outcome.
This is the only path from the engine to the desktop, files, shell and credential broker (§6, §10.1).
What an authorised action does lives in ofa.effects; dictation rules live in ofa.dictation."""
from __future__ import annotations

import asyncio

from .action_context import describe
from .audit import Audit
from .dictation import paraphrases_dictation, prepare_dictation
from .effects import run_effect
from .harness.api import Harness, HarnessError
from .memory import Memory
from .policy import Action, ApprovalState, ApprovalStore, PolicyDenied, TurnLog, classify_tier
from .vault.broker import Broker

OUTBOUND = {"send", "post", "forward", "share", "publish", "submit", "apply", "upload", "attach", "comment",
            "approve", "push", "merge", "pay", "purchase", "book", "order", "phone_send"}


class Executor:
    def __init__(self, harness: Harness, approvals: ApprovalStore, turns: TurnLog, audit: Audit, memory: Memory,
                 broker: Broker | None, speak, listen, epoch, lang=lambda: "en", show=lambda *_: None,
                 listen_dictation=None, pause_gate=None):
        self.h, self.approvals, self.turns, self.audit, self.memory = harness, approvals, turns, audit, memory
        self.broker, self.speak, self.listen, self.epoch, self.lang, self.show = broker, speak, listen, epoch, lang, show
        self.listen_dictation = listen_dictation or listen
        self.pause_gate = pause_gate          # awaited before each action; holds while the user said "pause"
        self.task = "t0"
        self.last_user_words = ""
        self.plan_approved: str | None = None
        self.effects_this_turn = 0
        self.tier2_this_turn = 0
        self._last_tier = 2

    def new_turn(self, task: str, words: str) -> None:
        self.task, self.last_user_words = task, words
        self.plan_approved, self.effects_this_turn, self.tier2_this_turn = None, 0, 0

    # --- main entry -------------------------------------------------------------------------
    async def run(self, action: Action) -> dict:
        result = await self._run(action)
        result.setdefault("tier", self._last_tier)
        return result

    async def _run(self, action: Action) -> dict:
        if self.pause_gate is not None:
            await self.pause_gate()               # spoken "pause" holds here; "stop" changes the epoch
        epoch = self.epoch()
        self._last_tier = 2
        action = describe(self.h, action)
        if paraphrases_dictation(action, self.last_user_words):
            return {"status": "rejected", "reason": "VERBATIM_MISMATCH",
                    "detail": "The user dictated: type their exact words (use dictate), or mode=compose only if they asked you to write it."}
        if action.verb == "dictate":
            prepared = await prepare_dictation(action, self.last_user_words, self.speak, self.listen,
                                               self.listen_dictation, self.memory.get("script", "roman"))
            if isinstance(prepared, dict):
                return prepared
            action = prepared
        tier = classify_tier(action, self.turns, epoch)
        self._last_tier = tier
        effectful = tier >= 1 and action.args.get("op") not in {"screen", "windows", "wait_for", "read_file", "files"}
        if effectful:
            self.effects_this_turn += 1
        if tier == 2:
            self.tier2_this_turn += 1
            if self.plan_needed():
                return {"status": "blocked", "reason": "PLAN_REQUIRED",
                        "detail": "This is a multi-step consequential task: call propose_plan first."}
            idem = action.digest()
            prior = self.memory.ledger_get(idem)
            if prior == "done" and action.verb in OUTBOUND:
                return {"status": "skipped", "reason": "ALREADY_DONE", "detail": "This exact action already succeeded; not repeating it."}
            if prior == "unknown" and action.verb in OUTBOUND:
                return {"status": "blocked", "reason": "OUTCOME_UNKNOWN",
                        "detail": "A previous identical attempt has an unknown outcome. Check the destination first, or ask the user."}
            self.show("approval", action)
            req = await self.approvals.obtain(action, self.speak, self.listen, self.lang())
            self.audit.write("approval", epoch=epoch, task=self.task, tier=2, digest=req.digest, result=req.state.value,
                             handle_ids=[action.handle] if action.handle else [])
            self.show("approval_done", None)
            if req.state != ApprovalState.GRANTED:
                out = {"status": "not_approved", "state": req.state.value}
                if req.state == ApprovalState.MODIFY:
                    out["user_said"] = req.transcript
                return out
            try:
                self.approvals.consume(req.id, action, self.epoch())
            except PolicyDenied as exc:
                return {"status": "refused", "reason": exc.code}
            for dest in action.destinations or [action.target or action.verb]:
                self.memory.ledger_set(self.task, idem, dest, action.verb, "intent")
        elif self.epoch() != epoch:
            return {"status": "cancelled", "reason": "SESSION_STOPPED"}
        if self.epoch() != epoch:
            return {"status": "cancelled", "reason": "SESSION_STOPPED"}
        try:
            result = await asyncio.to_thread(run_effect, self.h, self.memory, self.broker, action)
        except HarnessError as exc:
            result = {"status": "error", "reason": exc.code, "detail": str(exc), "options": exc.options}
        except PolicyDenied as exc:
            result = {"status": "refused", "reason": exc.code}
        except PermissionError as exc:
            result = {"status": "handoff", "reason": "INPUT_BLOCKED", "detail": str(exc)}
        except Exception as exc:   # report honestly; never claim success
            result = {"status": "error", "reason": type(exc).__name__, "detail": str(exc)[:200]}
        result.setdefault("status", "ok")
        if action.args.get("op") in {"open", "click", "double_click", "right_click", "key", "focus", "type",
                                     "replace", "dictate", "scroll_up", "scroll_down", "close"} and result["status"] != "cancelled":
            g = await asyncio.to_thread(self.h.glance)
            if g:
                result["now"] = g
        if tier == 2:
            idem = action.digest()
            verified = result["status"] == "ok" and result.get("verified", result.get("screen_changed", False))
            state = "done" if verified else ("failed" if result["status"] in {"error", "refused"} else "unknown")
            for dest in action.destinations or [action.target or action.verb]:
                self.memory.ledger_set(self.task, idem, dest, action.verb, state)
            result["outcome"] = state
        self.audit.write("action", epoch=epoch, task=self.task, tier=tier, digest=action.digest(),
                         result=result["status"], detail=action.verb,
                         handle_ids=[action.handle] if action.handle else [])
        result["tier"] = tier
        return result

    def plan_needed(self) -> bool:
        return self.plan_approved is None and (self.tier2_this_turn >= 2 or
                                               (self.tier2_this_turn >= 1 and self.effects_this_turn >= 5))

    async def approve_plan(self, steps: list[str]) -> dict:
        text = "Here is my plan. " + " ".join(f"{i + 1}. {s.rstrip('.')}." for i, s in enumerate(steps[:12]))
        action = Action(verb="plan", payload="\n".join(steps), args={"op": "plan"})
        req = await self.approvals.obtain(action, self.speak, self.listen, self.lang(),
                                          spoken=text + " Should I go ahead?")
        self.audit.write("plan", epoch=self.epoch(), task=self.task, digest=req.digest, result=req.state.value)
        if req.state == ApprovalState.GRANTED:
            self.approvals.consume(req.id, action, self.epoch())
            self.plan_approved = req.digest
            return {"status": "approved", "note": "Each consequential step will still be confirmed when it happens."}
        out = {"status": req.state.value}
        if req.transcript:
            out["user_said"] = req.transcript
        return out
