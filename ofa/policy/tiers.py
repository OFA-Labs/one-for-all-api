"""Tier classifier (§6). Unknown → 2. A model hint can raise a tier, never lower it."""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

from .action import Action

TIER0 = {"screen", "find_text", "read", "read_screen", "scroll", "navigate", "browse", "search_public",
         "wait_for", "focus", "switch", "minimize", "maximize", "restore", "arrange", "observe",
         "screenshot_local", "list_windows", "list_apps", "draft", "copy", "speak", "ask_user",
         "open_settings_page", "read_file", "list_files", "goal_step", "remember", "hover", "select",
         "list_processes"}
TIER1 = {"open", "close", "sign_in", "fill", "type_text", "dictate", "paste", "file_write_new", "click", "key",
         "launch", "system_control"}
# Tier 1 verbs that are direct device controls: the request itself is the authority, no target to name.
NO_TARGET = {"click", "key", "type_text", "dictate", "paste", "system_control"}
TIER2 = {"send", "post", "forward", "share", "publish", "submit", "apply", "upload", "attach", "comment",
         "approve", "push", "merge", "delete", "overwrite", "pay", "purchase", "book", "order",
         "create_account", "change_password", "change_security", "change_permission", "grant_permission",
         "run_command", "search_private", "release_otp", "file_write", "install", "uninstall", "sign_out",
         "change_setting", "phone_send", "clipboard_read", "end_process"}
ANSWER_LABEL = re.compile(r"\b(accept|answer|pick up|join|receive)\b", re.I)
ANSWER_WORDS = re.compile(r"\b(pick (it |the call )?up|answer|accept|receive|join|uthao|utha lo|utha do|"
                          r"uthaa|receive karo|call lo)\b", re.I)
CLIPBOARD_WORDS = re.compile(r"\b(clipboard|copied|paste)\b", re.I)

EFFECT_WORDS = re.compile(
    r"\b(send|post|submit|pay|purchase|buy|order|book|delete|remove|trash|discard|share|publish|merge|"
    r"approve|apply|upload|attach|transfer|checkout|check out|place order|sign up|create account|"
    r"confirm|forward|tweet|reply all|comment|save changes|overwrite|replace|install|uninstall|"
    r"unsubscribe|accept|grant|allow|bhejo|bhejein|bhejen|bhej)\b|"
    r"भेजें|भेजो|भेज|भुगतान|हटाएं|हटाएँ|मिटाएं|जमा करें|साझा करें|खरीदें|पोस्ट", re.I)
SEND_CONTEXTS = {"compose", "message", "chat", "terminal", "command", "comment", "form", "search_private"}
SEND_KEYS = {"enter", "return", "ctrl+enter", "ctrl+return", "cmd+enter", "alt+s", "ctrl+shift+enter"}
READONLY_COMMANDS = re.compile(r"^\s*(ls|dir|pwd|cd|cat|type|echo|git (status|diff|log|show|branch)|"
                               r"where|which|whoami|python --version|node --version)\b[^|;&><`$]*$", re.I)
# Files that hold credentials. OFA never reads them by itself; a shell command naming one needs a spoken yes.
SECRET_FILE = re.compile(r"(^|[\\/\s\"'])(\.env[\w.-]*|[\w.-]*\.(env|key|pem|pfx|p12|kdbx|dat)|credentials[\w.-]*|"
                         r"id_(rsa|ed25519|ecdsa)[\w.-]*)(?=$|[\s\"';|&)])", re.I)


@dataclass
class TurnLog:
    """What the user actually said this epoch. Written only by the speech pipeline."""
    epoch: int = 0
    turns: dict[str, str] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, turn_id: str, text: str, epoch: int) -> None:
        with self._lock:
            if epoch != self.epoch:
                self.epoch, self.turns = epoch, {}
            self.turns[turn_id] = text

    def names(self, turn_id: str | None, target: str | None, epoch: int) -> bool:
        if not turn_id or not target or epoch != self.epoch:
            return False
        said = self.turns.get(turn_id, "").casefold()
        tokens = [t for t in re.split(r"[\s/._:\-]+", target.casefold()) if len(t) >= 3
                  and t not in {"https", "http", "www", "com", "exe", "app"}]
        return bool(said) and bool(tokens) and any(t in said for t in tokens)


def said(turns: TurnLog | None, turn_id: str | None, epoch: int, pattern: re.Pattern) -> bool:
    """Did the user's own words this turn (never tool or screen text) match?"""
    if not turns or not turn_id or epoch != turns.epoch:
        return False
    return bool(pattern.search(turns.turns.get(turn_id, "")))


def classify_tier(action: Action, turns: TurnLog | None = None, epoch: int = 0) -> int:
    verb = action.verb
    if verb in TIER2:
        tier = 2
    elif verb == "run_command_readonly":
        readonly = bool(action.payload) and READONLY_COMMANDS.match(action.payload) is not None
        tier = 0 if readonly and not SECRET_FILE.search(action.payload) else 2
    elif verb in TIER0:
        tier = 0
    elif verb in TIER1:
        tier = 1
    else:
        tier = 2
    # A click on a bare screen point OFA cannot name could be anything: ask.
    if verb == "click" and action.args.get("x") is not None and not action.element_label:
        tier = 2
    # Effects hidden behind ordinary clicks/keys (§6 "any Tier 2 effect").
    if verb in {"click", "key", "select", "hover"} and action.element_label and EFFECT_WORDS.search(action.element_label):
        tier = 2
    if verb == "key" and (action.key or "").lower().replace(" ", "") in SEND_KEYS and (action.context or "") in SEND_CONTEXTS:
        tier = 2
    if verb in {"type_text", "paste", "dictate"} and "\n" in (action.payload or "") and (action.context or "") in {"terminal", "command", "chat", "message"}:
        tier = 2   # a newline would submit
    # Every use of a private item (vault or password manager) needs a spoken yes; sessions carry no secret.
    if verb == "fill" and action.handle and action.handle.startswith(("vault:", "pm:")):
        tier = 2
    if verb == "change_setting" or (verb == "open_settings_page" and action.context == "security"):
        tier = max(tier, 2 if verb == "change_setting" else 0)
    # Answering a call the user asked to pick up: the button says "Accept", but the user already said so.
    if (verb == "click" and action.context == "incoming_call" and ANSWER_LABEL.search(action.element_label or "")
            and said(turns, action.authorized_by_turn, epoch, ANSWER_WORDS)):
        tier = 1
    if verb == "clipboard_read" and said(turns, action.authorized_by_turn, epoch, CLIPBOARD_WORDS):
        tier = 1
    # Tier 1 needs the user's own words naming the target in this epoch; otherwise ask.
    if tier == 1 and verb not in NO_TARGET:
        named = turns and any(turns.names(action.authorized_by_turn, ref, epoch)
                              for ref in (action.target, action.handle.split("/", 1)[-1] if action.handle else None))
        if not named:
            tier = 2
    # Searching a private source the user named themselves ("search my Downloads") is a direct command.
    if verb == "search_private" and turns and turns.names(action.authorized_by_turn, action.target, epoch):
        tier = 1
    if action.tier_hint is not None and action.tier_hint > tier:
        tier = min(2, action.tier_hint)
    return tier
