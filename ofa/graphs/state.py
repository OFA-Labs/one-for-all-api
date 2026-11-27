"""Typed state for every OFA graph.

Values stay JSON-friendly (dicts, lists, strings, numbers) so the SQLite checkpointer can save a paused task.
A subgraph shares state with its parent through keys that appear in both schemas; keys used only inside a
subgraph stay inside it.
"""
from __future__ import annotations

from typing import Any, TypedDict


class Question(TypedDict):
    """What every interrupt() hands to the voice front end: say this, then listen."""
    kind: str        # approval | ask_user | remember | dictation | confirm | engine_wait
    say: str         # spoken before listening; "" means keep listening without speaking again
    timeout: float   # seconds to listen after speaking
    mode: str        # command | dictation (longer pauses allowed)


class Answer(TypedDict, total=False):
    """What the voice front end resumes a paused graph with."""
    heard: dict | None       # ofa.policy.approval.Heard fields, or None for silence
    tts_end: float           # monotonic time OFA finished speaking the question
    listen_started: float    # monotonic time listening began


class ApprovalFlow(TypedDict, total=False):
    action: dict             # in: the exact Action to approve (model_dump)
    spoken: str | None       # in: optional custom wording (plans)
    approval: dict           # inside: request id, prompts, attempt, deadline
    verdict: str             # out: ApprovalState value
    verdict_text: str | None  # out: what the user said
    approval_id: str         # out


class HandsState(TypedDict, total=False):
    # shared with the brain
    call: dict               # {id, name, args_json} from the engine
    text: str                # the user's own words this turn
    turn_id: str
    task: str
    plan_approved: str | None
    effects_this_turn: int
    tier2_this_turn: int
    tool_out: dict | None    # out: result handed back to the engine
    action_info: dict | None  # out: compact record for the spoken report
    # inside hands (and shared with the approval subgraph)
    action: dict
    spoken: str | None
    verdict: str
    verdict_text: str | None
    approval_id: str
    tier: int
    hands_epoch: int
    dictation: dict
    consumed_at: float
    route: str


class BrainState(TypedDict, total=False):
    text: str
    confidence: float | None
    turn_id: str
    task: str
    epoch: int
    messages: list[dict]
    calls: list[dict]        # tool calls from the last engine reply still to run, in order
    call: dict
    tool_out: dict | None
    action_info: dict | None
    finished: list | None    # [status, summary] once the engine called finish (or OFA stopped it)
    spoken_parts: list[str]
    actions: list[dict]
    seen: dict[str, int]     # loop detector: same call + same result
    step: int
    retries: int
    engine_error: dict | None
    plan_approved: str | None
    effects_this_turn: int
    tier2_this_turn: int
    result: dict | None      # TurnResult fields
    route: str


class TurnState(TypedDict, total=False):
    text: str
    confidence: float | None
    result: dict | None
    route: str


def jsonable(value: Any) -> Any:
    """Effect results may hold objects; checkpoints and engine messages need plain JSON."""
    import json
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))
