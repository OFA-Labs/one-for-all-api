"""The engine's tool surface (finite verbs, generic targets). Compact on purpose: Groq's dev tier allows
~8K tokens/minute, so every schema token counts. Calls are converted to policy Actions here."""
from __future__ import annotations

import json

from .policy.action import Action


def _fn(name, desc, props, req=()):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props, "required": list(req)}}}


S = {"type": "string"}
I = {"type": "integer"}
EFFECTS = ["none", "send", "post", "submit", "apply", "share", "upload", "attach", "comment", "delete", "pay",
           "purchase", "book", "order", "merge", "push", "approve", "publish", "forward", "create_account",
           "change_setting", "change_password", "install", "uninstall", "sign_out"]

TOOLS = [
    _fn("open", "Open an app, URL, file/folder path or ms-settings: page.", {"target": S}, ["target"]),
    _fn("windows", "List open windows.", {}),
    _fn("screen", "Read a window's UI elements (default front). Lines: id role \"text\" =value.",
        {"window": S, "ocr": {"type": "boolean"}}),
    _fn("look", "See the whole screen (pop-ups, calls, notifications, icons, apps screen can't read). Returns "
        "numbered marks m1.. and, with a question, the matching mark or point.",
        {"question": S, "scope": {"type": "string", "enum": ["screen", "window"]}, "window": S}),
    _fn("act", "One UI action. kind: click|double_click|right_click|type|replace|key|scroll_up|scroll_down|focus|close|"
        "minimize|maximize|restore|snap_left|snap_right|drag|wait_for. element=id from screen. effect+to+account for "
        "anything outbound/destructive. x,y: a screen point from look (unmarked icons only). Result includes a "
        "fresh short reading (now).",
        {"kind": S, "element": S, "text": S, "keys": S, "window": S, "effect": {"type": "string", "enum": EFFECTS},
         "to": {"type": "array", "items": S}, "account": S, "to_element": S, "x": I, "y": I}, ["kind"]),
    _fn("dictate", "Type the user's exact last words (verbatim) into an element; or mode=compose with text you drafted.",
        {"element": S, "mode": {"type": "string", "enum": ["verbatim", "compose"]}, "text": S}, ["element"]),
    _fn("fill_secret", "Fill a vault/password-manager handle into a field. You never see values.",
        {"handle": S, "element": S}, ["handle", "element"]),
    _fn("files", "Find files by name words in a scope (downloads|documents|desktop|pictures|home or a path).",
        {"query": S, "scope": S}, ["query"]),
    _fn("read_file", "Read a text file (first 8 KB).", {"path": S}, ["path"]),
    _fn("write_file", "Create or overwrite a text file.", {"path": S, "text": S}, ["path", "text"]),
    _fn("run_command", "Run a shell command (PowerShell). Read-only commands run directly; others need approval.",
        {"command": S, "cwd": S}, ["command"]),
    _fn("ask_user", "Ask the user a short spoken question and get their answer.", {"question": S}, ["question"]),
    _fn("propose_plan", "For complex tasks: speak a numbered plan and get approval before acting.",
        {"steps": {"type": "array", "items": S}}, ["steps"]),
    _fn("remember", "Save a mapping for later (e.g. 'my manager' -> 'Priya Shah') after the user agreed.",
        {"key": S, "value": S}, ["key", "value"]),
    _fn("resolve", "Resolve a reference like 'that one', 'the second result', 'my manager'.", {"ref": S}, ["ref"]),
    _fn("results", "Store candidate results found while searching, best first.", {"items": {"type": "array", "items": S}},
        ["items"]),
    _fn("finish", "End the task. status: done|partial|failed|blocked. summary: one short spoken sentence.",
        {"status": {"type": "string", "enum": ["done", "partial", "failed", "blocked"]}, "summary": S}, ["status", "summary"]),
]
TOOL_NAMES = {t["function"]["name"] for t in TOOLS}

KIND_TO_VERB = {"click": "click", "double_click": "click", "right_click": "click", "type": "type_text",
                "replace": "type_text", "key": "key", "scroll_up": "scroll", "scroll_down": "scroll", "focus": "focus",
                "close": "close", "minimize": "minimize", "maximize": "maximize", "restore": "restore",
                "snap_left": "arrange", "snap_right": "arrange", "drag": "click", "wait_for": "wait_for"}


class ToolArgError(ValueError):
    pass


def _point(args: dict) -> bool:
    return isinstance(args.get("x"), (int, float)) and isinstance(args.get("y"), (int, float)) and not args.get("element")


def parse_args(raw: str) -> dict:
    try:
        data = json.loads(raw or "{}")
    except json.JSONDecodeError as exc:
        raise ToolArgError("arguments were not valid JSON") from exc
    if not isinstance(data, dict):
        raise ToolArgError("arguments must be an object")
    return data


def to_action(name: str, args: dict, turn_id: str | None, label: str | None = None, role: str | None = None,
              context: str | None = None) -> Action:
    """Map a tool call to the Action the policy classifies. `label/role/context` come from the harness's
    own last reading (not from the model) so a Send button is recognised even if the model says effect=none."""
    if name == "open":
        return Action(verb="open", target=str(args.get("target", ""))[:500], authorized_by_turn=turn_id,
                      args={"op": "open"})
    if name == "act":
        kind = str(args.get("kind", ""))
        if kind not in KIND_TO_VERB:
            raise ToolArgError(f"unknown kind {kind!r}")
        effect = args.get("effect") or "none"
        verb = effect if effect != "none" else KIND_TO_VERB[kind]
        to = [str(x)[:120] for x in (args.get("to") or [])][:10]
        return Action(verb=verb, target=args.get("window") or args.get("element"), payload=args.get("text"),
                      destinations=to, account=args.get("account"), element_label=label, element_role=role,
                      key=args.get("keys"), context=context, authorized_by_turn=turn_id,
                      args={"op": kind, "element": args.get("element"), "window": args.get("window"),
                            "to_element": args.get("to_element"),
                            **({"x": int(args["x"]), "y": int(args["y"])} if _point(args) else {})})
    if name == "dictate":
        return Action(verb="dictate", target=args.get("element"), payload=args.get("text"), context=context,
                      authorized_by_turn=turn_id, args={"op": "dictate", "element": args.get("element"),
                                                        "mode": args.get("mode", "verbatim")})
    if name == "fill_secret":
        return Action(verb="fill", handle=args.get("handle"), target=args.get("element"), authorized_by_turn=turn_id,
                      args={"op": "fill_secret", "element": args.get("element")})
    if name == "files":
        scope = str(args.get("scope") or "home")
        return Action(verb="search_private" if scope else "list_files", target=scope, payload=args.get("query"),
                      authorized_by_turn=turn_id, args={"op": "files"})
    if name == "read_file":
        return Action(verb="read_file", target=args.get("path"), args={"op": "read_file"})
    if name == "write_file":
        from pathlib import Path
        path = str(args.get("path") or "")
        return Action(verb="file_write", target=path, payload=args.get("text"), exists=bool(path) and Path(path).exists(),
                      args={"op": "write_file"})
    if name == "run_command":
        return Action(verb="run_command_readonly", payload=args.get("command"), target=args.get("cwd"),
                      args={"op": "run_command"})
    if name in {"screen", "windows"}:
        return Action(verb="screen", target=args.get("window"), args={"op": name, "ocr": args.get("ocr")})
    raise ToolArgError(f"{name} is not an action tool")
