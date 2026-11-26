"""Spoken, single-use, digest-bound approvals (§6), enforced in code below the engine.

The engine never sees a grant. A grant exists only after the speech listener delivers a mic
transcript (not echo) that the lexicon classifies YES inside the window opened for that request.
"""
from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable
from uuid import uuid4

from . import lexicon
from .action import Action


class PolicyDenied(RuntimeError):
    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class ApprovalState(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    MODIFY = "modify"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    CONSUMED = "consumed"


VERB_EN = {"send": "send", "post": "post", "forward": "forward", "share": "share", "publish": "publish",
           "submit": "submit", "apply": "submit the application", "upload": "upload", "attach": "attach",
           "comment": "post the comment", "approve": "approve", "push": "push", "merge": "merge",
           "delete": "delete", "overwrite": "overwrite", "pay": "pay", "purchase": "buy", "book": "book",
           "order": "place the order", "create_account": "create an account", "run_command": "run the command",
           "change_password": "change the password", "change_security": "change a security setting",
           "change_permission": "change permissions", "grant_permission": "grant a permission",
           "search_private": "search", "release_otp": "use the one-time code", "file_write": "save a file",
           "run_command_readonly": "run the command",
           "install": "install", "uninstall": "uninstall", "change_setting": "change the setting",
           "click": "press", "key": "press", "fill": "fill in", "plan": "run this plan",
           "phone_send": "send from your phone", "sign_out": "sign out of", "open": "open", "close": "close",
           "sign_in": "sign in to", "type_text": "type into", "paste": "paste into"}
SHORT = 280


def render_spoken(action: Action, lang: str = "en") -> str:
    verb = VERB_EN.get(action.verb, action.verb.replace("_", " "))
    parts: list[str] = []
    if action.verb in {"click", "key"}:
        parts.append(f"I'm about to press {action.element_label or action.key or 'this control'}")
        if action.target:
            parts.append(f"in {action.target}")
    elif action.verb == "file_write" and action.exists:
        parts.append("I'm about to overwrite the existing file")
    else:
        parts.append(f"I'm about to {verb}")
    if action.payload and action.verb != "run_command":
        text = action.payload.strip()
        parts.append(f': "{text}"' if len(text) <= SHORT else
                     f": a {len(text.split())}-word text shown on your screen, starting \"{text[:80]}\"")
    elif action.payload:
        parts.append(f": {action.payload[:SHORT]}")
    if action.file_names:
        parts.append("with the file " + ", ".join(action.file_names))
    if action.destinations:
        parts.append(("to " if action.verb not in {"search_private"} else "in ") + ", and ".join(action.destinations))
    elif action.target and action.verb not in {"click", "key"}:
        parts.append(f"on {action.target}")
    if action.account:
        parts.append(f"from the account {action.account}")
    question = "Should I go ahead?"
    if lang == "hi":
        question = "Kya main aage badhoon? Haan ya nahi boliye."
    return " ".join(parts).replace(" :", ":") + ". " + question


@dataclass
class ApprovalRequest:
    id: str
    epoch: int
    action_id: str
    digest: str
    spoken: str
    created: float
    expires: float
    state: ApprovalState = ApprovalState.PENDING
    transcript: str | None = None
    destinations: tuple[str, ...] = ()


@dataclass
class Heard:
    text: str
    confidence: float | None = None
    source: str = "mic"          # mic | loopback | text | tool
    echo: bool = False
    started: float = field(default_factory=time.monotonic)


Speak = Callable[[str], Awaitable[float]]           # returns monotonic time TTS finished
Listen = Callable[[float], Awaitable["Heard | None"]]


class ApprovalStore:
    def __init__(self, ttl: float = 45.0, window: float = 8.0, echo_gap: float = 0.4):
        self.ttl, self.window, self.echo_gap = ttl, window, echo_gap
        self.epoch = 0
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = threading.RLock()
        self.on_event: Callable[[str, ApprovalRequest], None] | None = None

    # --- lifecycle -------------------------------------------------------------------------
    def set_epoch(self, epoch: int) -> None:
        with self._lock:
            if epoch != self.epoch:
                self.invalidate_all()
            self.epoch = epoch

    def invalidate_all(self) -> int:
        with self._lock:
            n = 0
            for req in self._requests.values():
                if req.state in (ApprovalState.PENDING, ApprovalState.GRANTED):
                    req.state = ApprovalState.INVALIDATED
                    n += 1
            return n

    def ask(self, action: Action, lang: str = "en", spoken: str | None = None) -> ApprovalRequest:
        now = time.monotonic()
        req = ApprovalRequest(id=uuid4().hex, epoch=self.epoch, action_id=action.id, digest=action.digest(),
                              spoken=spoken or render_spoken(action, lang), created=now, expires=now + self.ttl,
                              destinations=tuple(action.destinations))
        if len(action.destinations) > 1 and not all(d in req.spoken for d in action.destinations):
            raise PolicyDenied("DESTINATIONS_NOT_STATED", "Every destination must be spoken in the request")
        with self._lock:
            self._requests[req.id] = req
        self._emit("asked", req)
        return req

    def get(self, req_id: str) -> ApprovalRequest:
        return self._requests[req_id]

    # --- decision (speech pipeline only) ---------------------------------------------------
    def decide(self, req_id: str, heard: Heard, tts_end: float = 0.0) -> ApprovalState:
        with self._lock:
            req = self._requests.get(req_id)
            if req is None or req.state != ApprovalState.PENDING:
                return req.state if req else ApprovalState.INVALIDATED
            if req.epoch != self.epoch:
                req.state = ApprovalState.INVALIDATED
                return req.state
            if time.monotonic() > req.expires:
                req.state = ApprovalState.EXPIRED
                return req.state
            if heard.source != "mic" or heard.echo or heard.started < tts_end + self.echo_gap:
                return ApprovalState.PENDING          # not admissible; keep waiting
            verdict = lexicon.classify(heard.text, heard.confidence)
            req.transcript = heard.text
            if verdict == lexicon.YES:
                req.state = ApprovalState.GRANTED
            elif verdict == lexicon.NO:
                req.state = ApprovalState.DENIED
            elif verdict == lexicon.MODIFY:
                req.state = ApprovalState.MODIFY
            else:
                return ApprovalState.PENDING
        self._emit(req.state.value, req)
        return req.state

    def expire(self, req_id: str) -> None:
        with self._lock:
            req = self._requests.get(req_id)
            if req and req.state == ApprovalState.PENDING:
                req.state = ApprovalState.EXPIRED

    # --- enforcement (executor, immediately before the effect) -------------------------------
    def consume(self, req_id: str, action: Action, epoch: int) -> None:
        with self._lock:
            req = self._requests.get(req_id)
            if req is None:
                raise PolicyDenied("NO_APPROVAL")
            if req.state == ApprovalState.CONSUMED:
                raise PolicyDenied("APPROVAL_SPENT", "Approval was already used")
            if req.state != ApprovalState.GRANTED:
                raise PolicyDenied("NOT_APPROVED", f"Approval state is {req.state.value}")
            if req.epoch != epoch or epoch != self.epoch:
                req.state = ApprovalState.INVALIDATED
                raise PolicyDenied("EPOCH_CHANGED", "Session was stopped or restarted")
            if time.monotonic() > req.expires:
                req.state = ApprovalState.EXPIRED
                raise PolicyDenied("APPROVAL_EXPIRED")
            if action.digest() != req.digest:
                req.state = ApprovalState.INVALIDATED
                raise PolicyDenied("PAYLOAD_CHANGED", "The action changed after approval")
            req.state = ApprovalState.CONSUMED
        self._emit("consumed", req)

    # --- spoken flow ---------------------------------------------------------------------------
    async def obtain(self, action: Action, speak: Speak, listen: Listen, lang: str = "en",
                     spoken: str | None = None) -> ApprovalRequest:
        req = self.ask(action, lang, spoken)
        prompts = [req.spoken, "Should I go ahead? Please say yes or no." if lang != "hi"
                   else "Haan ya nahi boliye."]
        for prompt in prompts:
            if req.state != ApprovalState.PENDING:
                break
            tts_end = await speak(prompt)
            deadline = time.monotonic() + self.window
            while req.state == ApprovalState.PENDING and time.monotonic() < deadline:
                heard = await listen(max(0.1, deadline - time.monotonic()))
                if heard is None:
                    break
                self.decide(req.id, heard, tts_end)
        if req.state == ApprovalState.PENDING:
            self.expire(req.id)
        return req

    def _emit(self, kind: str, req: ApprovalRequest) -> None:
        if self.on_event:
            try:
                self.on_event(kind, req)
            except Exception:
                pass


async def no_listen(_: float) -> None:
    await asyncio.sleep(0)
    return None
