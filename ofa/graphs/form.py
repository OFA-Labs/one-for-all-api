"""Form subgraph: fill a multi-page web form, asking only what OFA cannot answer.

    scan ─▶ map ─▶ queue ─▶ act[HANDS] ─▶ queue …                         (type known answers)
      ▲      │        └─▶ ask ─▶ queue …                                   (your answers, asked while typing)
      │      └─▶ blocked / handoff
      │   queue empty ─▶ check ─┬─▶ map (new or failed questions, 2 rounds)
      │                         ├─▶ queue Next ─▶ act ─▶ turned ─▶ scan
      └─────────────────────────┴─▶ review ─▶ queue Submit ─▶ act (spoken yes) ─▶ confirm ─▶ save_offer ─▶ END

The model only maps facts to questions (one call per page). Every click and keystroke goes through the hands
graph, so tiers, approvals, the ledger and the audit apply. Private fields, declarations and Submit always need
your own voice.
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict
from typing import TypedDict
from urllib.parse import urlsplit

from langgraph.graph import END, START, StateGraph

from ..egress import EGRESS, LeakBlocked
from ..engine.base import EngineError, TextDelta, ToolCall
from ..eyes.form import Field, FormPage, Option, read_form, submission_readback
from ..forms import (CAPTCHA, SKIP, SPEED, entries_in, local_answers, match_option, model_messages,
                     needs_user, parse_answers, question_prompt, shows,
                     unanswered)
from ..harness.api import HarnessError, norm
from ..policy import classify
from ..text.dictation import verbatim
from ..text.translit import apply_script
from ..tools import ToolArgError, parse_args
from .deps import Deps
from .hands import hands_graph
from .pauses import ask, heard_of

MAX_PAGES = 20
FACT_CHARS = 9000            # profile sections sent for a page with long answers (about 2,300 tokens)
SHORT_FACT_CHARS = 4000      # a page with only short or choice questions needs less
MAX_WAIT = 60                # a longer rate-limit wait is not worth it for someone in a hurry
ROUNDS = 2
NAV_WAIT = 12.0


class FormState(TypedDict, total=False):
    # shared with the brain and hands
    call: dict
    text: str
    turn_id: str
    task: str
    plan_approved: str | None
    effects_this_turn: int
    tier2_this_turn: int
    tool_out: dict | None
    action_info: dict | None
    finished: list | None
    # the form
    form_call: dict
    window: int | None
    speed: bool
    page: dict
    pages: int
    rounds: int
    queue: list[dict]          # actions still to run: {kind, element, text, field}
    asks: list[dict]           # questions for you: {field, reason, say}
    asked: list[str]           # field keys already asked on this page
    told: str                  # field key whose question is already being spoken while OFA types
    answered: dict             # field key -> {question, value, source}
    skipped: list[str]
    expect: dict               # field key -> value that must be read back from this page
    current: dict | None       # the action running in hands
    after: str                 # where to go when the queue is empty
    route: str


def _fields(page: dict) -> list[Field]:
    return [Field(**{**f, "options": [Option(**o) for o in f["options"]]}) for f in page["fields"]]


def form_graph(deps: Deps) -> StateGraph:
    speaking: dict[str, asyncio.Task] = {}          # a question spoken while typing continues

    def done(s: FormState, status: str, summary: str, extra: dict | None = None) -> dict:
        out = {"status": status, "summary": summary, "pages": s.get("pages", 0),
               "answered": len(s.get("answered") or {}), "skipped": s.get("skipped") or [], **(extra or {})}
        return {"tool_out": out, "finished": [status, summary], "call": s.get("form_call") or s["call"], "route": "end"}

    async def say(text: str) -> None:
        await deps.voice.speak(text)

    def start(s: FormState) -> dict:
        try:
            args = parse_args(s["call"]["args_json"])
        except ToolArgError:
            args = {}
        speed = bool(args.get("speed")) or bool(SPEED.search(s.get("text", "")))
        return {"form_call": s["call"], "window": args.get("window"), "speed": speed, "pages": 0, "rounds": 0,
                "queue": [], "asks": [], "asked": [], "told": "", "answered": {}, "skipped": [], "current": None, "expect": {},
                "plan_approved": s.get("plan_approved"), "action_info": None}

    async def scan(s: FormState) -> dict:
        deps.voice.display("acting", "Reading the form")
        try:
            page: FormPage = await asyncio.to_thread(read_form, deps.harness, s.get("window"))
        except HarnessError as exc:
            return done(s, "blocked", str(exc))
        if page.closed:
            return done(s, "blocked", "The form says it is closed and no longer accepting responses.")
        if page.done:
            return done(s, "partial", "The page says a response was recorded. I did not submit anything now; "
                                      "please check it.")
        if s["pages"] >= MAX_PAGES:
            return done(s, "partial", f"I stopped after {MAX_PAGES} pages.")
        data = page.as_state()
        captcha = CAPTCHA.search(" ".join([page.title, *(f.question for f in page.fields)]))
        update = {"page": data, "window": page.hwnd, "pages": s["pages"] + 1, "rounds": 0, "asked": [], "asks": [],
                  "queue": [], "told": "", "expect": {}}
        if captcha:
            return {**update, "route": "handoff"}
        if not page.fields and not page.nav:
            return done(s, "blocked", "I could not find any questions or buttons on this page.")
        label = f"Page {page.page[0]} of {page.page[1]}" if page.page else f"Page {update['pages']}"
        deps.voice.display("acting", label)
        if s["speed"] and page.page:
            await say(label)
        return {**update, "route": "map"}

    def handoff(s: FormState) -> dict:
        heard = heard_of(ask("confirm", "This page needs you: complete the human check, then say continue.", 90.0))
        if heard is None:
            return done(s, "blocked", "I'm waiting for you to complete the human check on this page.")
        return {"route": "scan"}

    async def map_answers(s: FormState) -> dict:
        """One model call: facts → answers. Private, declaration and file questions never go to the model."""
        fields = _fields(s["page"])
        open_fields = [f for f in fields if (unanswered(f) or f.error) and f.key() not in s["asked"]]
        mine = [(f, needs_user(f)) for f in open_fields]
        for f, reason in mine:
            if f.kind == "select" and not f.options and reason is None:
                try:
                    labels = await asyncio.to_thread(deps.harness.dropdown_options, f.id)
                except HarnessError:
                    labels = []
                f.options = [Option("", label) for label in labels]
        data = {**s["page"], "fields": [asdict(f) for f in fields]}
        candidates = [f for f, reason in mine if reason is None and not f.error]
        answers: dict[str, dict] = local_answers(candidates, deps.corpus.facts()) if candidates else {}
        for_model = [f for f in candidates if f.id not in answers]
        if for_model:
            budget = FACT_CHARS if any(f.kind == "long" for f in for_model) else SHORT_FACT_CHARS
            facts = [f.public() for f in deps.corpus.relevant([f.question + " " + f.help for f in for_model],
                                                               budget_chars=budget)]
            facts += [f"[answered earlier] {v['question']}: {v['value']}" for v in s["answered"].values()]
            page = f"{s['page']['page'][0]} of {s['page']['page'][1]}" if s["page"].get("page") else str(s["pages"])
            messages = model_messages(for_model, facts, s.get("text", ""), page)
            known = "\n".join(facts) + "\n" + s.get("text", "")
            try:
                tool_args, text = await ask_model(messages)
                if not entries_in(tool_args, text):             # an empty or unreadable reply: ask once more
                    tool_args, text = await ask_model(messages)
                answers.update(parse_answers(tool_args, text, for_model, known))
            except RuntimeError as exc:       # keep going: type what the profile answers, ask you the rest
                await say(f"{str(exc)[:120]} I'll ask you what I can't fill from your profile.")
        queue, asks, skipped = list(s["queue"]), [], list(s["skipped"])
        answered = dict(s["answered"])
        expect = dict(s.get("expect") or {})
        for f, reason in mine:
            a = answers.get(f.id, {"status": "missing"})
            if reason in {"sensitive", "file"}:
                asks.append({"field": f.id, "reason": reason, "say": ""})
            elif reason == "declare":
                asks.append({"field": f.id, "reason": "declare", "say": question_prompt(f, "declare", s["speed"])})
            elif reason in {"decision", "ambiguous"}:     # your choice, never the model's
                if f.required or f.error:
                    asks.append({"field": f.id, "reason": "missing", "say": question_prompt(f, "missing", s["speed"])})
                else:
                    skipped.append(f.question[:80])
            elif a["status"] == "missing" or f.error:
                if f.required or f.error:
                    why = "error" if f.error else "missing"
                    asks.append({"field": f.id, "reason": why, "say": question_prompt(f, why, s["speed"])})
                else:
                    skipped.append(f.question[:80])
            else:
                queue += actions_for(f, a["value"])
                answered[f.key()] = {"question": f.question[:160], "value": a["value"],
                                     "source": a.get("source") or "facts"}
                expect[f.key()] = a["value"]
        keys = {f.id: f.key() for f in fields}
        update = {"page": data, "queue": queue, "asks": asks, "answered": answered, "skipped": skipped, "after": "check",
                  "expect": expect,
                  "asked": s["asked"] + [keys[a_["field"]] for a_ in asks]}
        # Ask the first question while the known answers are being typed.
        first = next((a_ for a_ in asks if a_["say"]), None)
        if queue and first:
            deps.voice.expect()
            speaking[s["task"]] = asyncio.create_task(deps.voice.speak(first["say"]))
            update["told"] = first["field"]
        return {**update, "route": "queue"}

    async def ask_model(messages: list[dict]) -> tuple[str | None, str]:
        for attempt in range(4):
            tool_args, text, error = None, "", None
            async for event in deps.engine.stream(messages, []):      # plain JSON: long tool calls fail more often
                if isinstance(event, ToolCall):
                    tool_args = event.args_json
                elif isinstance(event, TextDelta):
                    text += event.text
                elif isinstance(event, EngineError):
                    error = event
            if error is None:
                return tool_args, text
            wait = max(1, int(error.retry_after or 5))
            if not (error.retryable and attempt < 3) or wait > MAX_WAIT:
                raise RuntimeError(error.user_message)
            await say(f"The model asked me to wait {wait} seconds.")
            await asyncio.sleep(wait)
        raise RuntimeError("The reasoning engine did not answer.")

    def actions_for(f: Field, value: str) -> list[dict]:
        if f.kind in {"radio", "check"}:
            wanted = [v.strip() for v in value.split(";")]
            return [{"kind": "click", "element": o.id, "field": f.id} for o in f.options
                    if o.label in wanted and not o.checked]
        if f.kind == "declare":
            return [{"kind": "click", "element": f.id, "field": f.id}]
        if f.kind == "select":
            return [{"kind": "select_option", "element": f.id, "text": value, "field": f.id}]
        return [{"kind": "replace", "element": f.id, "text": value, "field": f.id}]

    def queue_step(s: FormState) -> dict:
        if s["queue"]:
            item, rest = s["queue"][0], s["queue"][1:]
            args = {k: v for k, v in item.items() if k in {"kind", "element", "text", "effect", "to"}}
            if item.get("tool") == "fill_secret":
                args = {"handle": item["handle"], "element": item["element"]}
            call = {"id": f"form-{s['pages']}-{len(rest)}", "name": item.get("tool", "act"),
                    "args_json": json.dumps(args), "form": s["page"].get("url") or s["page"]["title"]}
            return {"queue": rest, "current": item, "call": call, "effects_this_turn": 0, "tier2_this_turn": 0,
                    "tool_out": None, "action_info": None, "route": "act"}
        if s["asks"]:
            return {"route": "ask"}
        return {"route": s["after"]}

    def after_act(s: FormState) -> dict:
        item, out = s["current"] or {}, s.get("tool_out") or {}
        if item.get("submit"):
            if out.get("status") in {"not_approved", "refused", "cancelled"}:
                return done(s, "partial", "I filled the form but did not submit it, because you did not say yes.")
            return {"route": "confirm"}
        if item.get("next"):
            return {"route": "turned"}
        if out.get("status") not in {"ok", "skipped"}:
            return {"skipped": s["skipped"] + [f"{item.get('field')}: {out.get('reason') or out.get('state')}"],
                    "route": "queue"}
        return {"route": "queue"}

    async def speech_done(s: FormState) -> dict:
        task = speaking.pop(s["task"], None)
        if task is not None:
            await task
        return {}

    def question(s: FormState) -> dict:
        item, rest = s["asks"][0], s["asks"][1:]
        f = next(x for x in _fields(s["page"]) if x.id == item["field"])
        if item["reason"] in {"sensitive", "file"}:
            return {"asks": rest, "current": item, "route": "private"}
        prompt = "" if item["field"] == s.get("told") else item["say"]
        heard = heard_of(ask("ask_user", prompt, 25.0, mode="dictation" if f.kind in {"text", "long"} else "command"))
        # ---- runs once, with your answer ----
        update = {"asks": rest, "told": "", "route": "queue"}
        if heard is None or not heard.text.strip() or SKIP.match(heard.text.strip()):
            return {**update, "skipped": s["skipped"] + [f.question[:80]]}
        if item["reason"] == "declare":
            if classify(heard.text, heard.confidence) != "YES":
                return {**update, "skipped": s["skipped"] + [f.question[:80]]}
            return {**update, "queue": s["queue"] + actions_for(f, "yes"),
                    "expect": {**(s.get("expect") or {}), f.key(): "yes"}}
        if f.options:
            picked = match_option(heard.text, [o.label for o in f.options])
            if picked is None:
                if item.get("retry"):
                    return {**update, "skipped": s["skipped"] + [f.question[:80]]}
                again = {**item, "retry": True, "say": "I didn't match that to an option. " + item["say"]}
                return {**update, "asks": [again, *rest]}
            value = picked
        else:
            value = verbatim(apply_script(heard.text, deps.memory.get("script", "roman"))).replace("\n", " ")
        answered = {**s["answered"], f.key(): {"question": f.question[:160], "value": value, "source": "you"}}
        return {**update, "answered": answered, "queue": s["queue"] + actions_for(f, value),
                "expect": {**(s.get("expect") or {}), f.key(): value}}

    def private(s: FormState) -> dict:
        """Passwords, ID or bank numbers and uploads: a saved private item (asked again in detail by hands),
        or you do it yourself."""
        item = s["current"]
        f = next(x for x in _fields(s["page"]) if x.id == item["field"])
        host = urlsplit(s["page"].get("url") or "").hostname or ""
        if item["reason"] == "sensitive":
            handle = private_handle(f.question, host)
            if handle:
                return {"queue": [{"tool": "fill_secret", "handle": handle, "element": f.id, "field": f.id}, *s["queue"]],
                        "route": "queue"}
            prompt = (f"This form asks for {f.question[:80]}. I won't fill it. Type it yourself and say continue, "
                      "or say skip.")
        else:
            prompt = f"{f.question[:80]} needs a file. Please attach it yourself and say continue, or say skip."
        heard = heard_of(ask("confirm", prompt, 60.0))
        skipped = s["skipped"] if heard and not SKIP.match(heard.text.strip()) else s["skipped"] + [f.question[:80]]
        return {"skipped": skipped, "route": "queue"}

    def private_handle(question: str, host: str) -> str | None:
        """A vault item saved for this site whose label fits the question. The broker re-checks the real origin."""
        if deps.broker is None or not host:
            return None
        words = set(norm(question).split())
        for item in deps.broker.vault.list():
            targets = " ".join(item.get("allowed_targets") or [])
            if host in targets and (set(item["label"].replace("-", " ").split()) & words or
                                    ("password" in item["label"] and "password" in words)):
                return item["handle"]
        return None

    async def check(s: FormState) -> dict:
        """Read back the page: unfilled fields, new questions that appeared after a choice."""
        try:
            page = await asyncio.to_thread(read_form, deps.harness, s["window"])
        except HarnessError as exc:
            return done(s, "blocked", str(exc))
        data = page.as_state()
        known = set(s["asked"]) | set(s["answered"])
        new = [f for f in page.fields if f.key() not in known and unanswered(f)]
        expect = s.get("expect") or {}
        mismatched = [f for f in page.fields
                      if not f.sensitive and f.key() in expect and not shows(f, expect[f.key()])]
        wrong = mismatched + [f for f in page.fields if f not in mismatched
                              and f.key() in s["answered"] and unanswered(f)]
        if (new or wrong) and s["rounds"] < ROUNDS:
            retry = []
            for f in wrong:
                retry += actions_for(f, expect.get(f.key()) or s["answered"][f.key()]["value"])
            if wrong and not new:
                return {"page": data, "rounds": s["rounds"] + 1, "queue": retry, "route": "queue"}
            return {"page": data, "rounds": s["rounds"] + 1, "queue": retry, "route": "map"}
        if mismatched:
            names = ", ".join(f.question[:60] for f in mismatched[:4])
            return done(s, "partial", f"I could not confirm {names}: the page does not show what I entered. "
                                      "I did not press Next or Submit.",
                        {"reason": "VERIFICATION_FAILED", "unverified": [f.question[:80] for f in mismatched]})
        if "next" in page.nav:
            return {"page": data, "queue": [{"kind": "click", "element": page.nav["next"], "next": True}],
                    "asks": [], "route": "queue"}
        if "submit" in page.nav:
            return {"page": data, "route": "review"}
        return done(s, "partial", "I filled this page but found no Next or Submit button.")

    async def turned(s: FormState) -> dict:
        """After Next: either a new page, or the same page with validation errors."""
        before = FormPage(**{**s["page"], "fields": _fields(s["page"])}).signature()
        deadline = time.monotonic() + NAV_WAIT
        while True:
            await asyncio.sleep(0.4)
            try:
                page = await asyncio.to_thread(read_form, deps.harness, s["window"])
            except HarnessError as exc:
                return done(s, "blocked", str(exc))
            if page.done or page.closed or page.signature() != before:
                return {"route": "scan"}
            if page.errors or time.monotonic() > deadline:
                break
        if page.errors and s["rounds"] < ROUNDS:
            return {"page": page.as_state(), "rounds": s["rounds"] + 1,
                    "asked": [k for k in s["asked"] if k not in {f.key() for f in page.fields if f.error}],
                    "route": "map"}
        why = f"The form says: {page.errors[0]}" if page.errors else "The page did not change after Next"
        return done(s, "partial", f"{why}. I stopped on page {s['pages']}.")

    async def review(s: FormState) -> dict:
        url = s["page"].get("url") or s["page"]["title"]
        if deps.memory.get(f"form_submitted:{url}"):
            return done(s, "blocked", "I already submitted this form, so I won't submit it twice.")
        mine = sum(1 for v in s["answered"].values() if v["source"] == "you")
        summary = (f"{s['pages']} pages filled: {len(s['answered']) - mine} answers from your profile, {mine} from you.")
        if s["skipped"]:
            summary += f" Left empty: {', '.join(x[:40] for x in s['skipped'][:4])}."
        await say(summary)
        host = urlsplit(url).hostname or url[:60]
        return {"queue": [{"kind": "click", "element": s["page"]["nav"]["submit"], "effect": "submit", "to": [host],
                           "submit": True}], "asks": [], "route": "queue"}

    async def confirm(s: FormState) -> dict:
        deadline = time.monotonic() + NAV_WAIT
        url = s["page"].get("url") or s["page"]["title"]
        seen = None
        while time.monotonic() < deadline:
            await asyncio.sleep(0.5)
            try:
                page = await asyncio.to_thread(read_form, deps.harness, s["window"])
            except HarnessError:
                continue
            proof = submission_readback(s["page"].get("url"), page)
            if proof == "verified":
                deps.memory.set(f"form_submitted:{url}", time.time())
                return {"route": "save_offer"}
            seen = seen or proof
            if page.errors:
                return done(s, "partial", f"Submit was refused. The form says: {page.errors[0]}.")
        if seen:
            # It may well have been sent, so it must not be sent again.
            deps.memory.set(f"form_submitted:{url}", time.time())
            return done(s, "partial", "I pressed Submit and the page says it was recorded, but I could not verify "
                                      "that from the page address. Please check it. I will not submit it again.")
        return done(s, "partial", "I pressed Submit but could not see a confirmation. Please check the page.")

    def save_offer(s: FormState) -> dict:
        new = [v for v in s["answered"].values() if v["source"] == "you"]
        submitted = {"tool": "fill_form", "verb": "submit", "status": "ok", "tier": 2, "verified": True,
                     "outcome": "done"}
        if new:
            heard = heard_of(ask("remember", f"Submitted. Should I save your {len(new)} new answers for next time?", 10.0))
            if heard is not None and classify(heard.text, heard.confidence) == "YES":
                for v in new:
                    try:
                        EGRESS.guard(v["value"], "corpus")
                    except LeakBlocked:
                        continue
                    deps.corpus.append("answers", v["question"], v["value"])
        return {**done(s, "done", "I filled and submitted the form."), "action_info": submitted}

    g = StateGraph(FormState)
    nodes = {"start": start, "scan": scan, "map": map_answers, "queue": queue_step, "speech_done": speech_done,
             "ask": question, "private": private, "check": check, "turned": turned, "review": review,
             "confirm": confirm, "save_offer": save_offer, "handoff": handoff, "after_act": after_act}
    for name, node in nodes.items():
        g.add_node(name, node)
    g.add_node("act", hands_graph(deps).compile())
    by_route = lambda s: END if s.get("route") == "end" else s["route"]
    g.add_edge(START, "start")
    g.add_edge("start", "scan")
    g.add_conditional_edges("scan", by_route, ["map", "handoff", END])
    g.add_conditional_edges("handoff", by_route, ["scan", END])
    g.add_conditional_edges("map", by_route, ["queue", END])
    g.add_conditional_edges("queue", lambda s: "speech_done" if s["route"] == "ask" else by_route(s),
                            ["act", "speech_done", "check", END])
    g.add_edge("act", "after_act")
    g.add_conditional_edges("after_act", by_route, ["queue", "confirm", "turned", END])
    g.add_edge("speech_done", "ask")
    g.add_conditional_edges("ask", by_route, ["queue", "private", END])
    g.add_conditional_edges("private", by_route, ["queue", END])
    g.add_conditional_edges("check", by_route, ["queue", "map", "review", END])
    g.add_conditional_edges("turned", by_route, ["scan", "map", END])
    g.add_conditional_edges("review", by_route, ["queue", END])
    g.add_conditional_edges("confirm", by_route, ["save_offer", END])
    g.add_edge("save_offer", END)
    return g
