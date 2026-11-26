"""Local capability grammar; targets are discovered data, never app-specific code."""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from difflib import get_close_matches

from hassil import Intents, TextChunk, TextSlotList, TextSlotValue, WildcardSlotList, recognize_all

from .language import language_of
from .websites import WebsiteResolver


def normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


@dataclass(frozen=True)
class Action:
    capability: str
    args: dict[str, str]


@dataclass(frozen=True)
class Intent:
    intent: str
    slots: dict[str, str]
    confidence: float
    language: str
    actions: tuple[Action, ...] = ()
    options: tuple[str, ...] = ()


class Router:
    def __init__(self, aliases: Mapping[str, str] | Iterable[tuple[str, str]],
                 language: str = "auto", websites: Mapping[str, str] | None = None) -> None:
        self.language = language
        self.websites = WebsiteResolver(websites)
        pairs = list(aliases.items() if isinstance(aliases, Mapping) else aliases)
        self.aliases = {normalize(alias): target for alias, target in pairs}
        values = [TextSlotValue(TextChunk(text=normalize(alias)), target)
                  for alias, target in pairs]
        self.slots = {"targets": TextSlotList(name="targets", values=values)}
        for name in ("subject", "filename", "artifact", "destination"):
            self.slots[name] = WildcardSlotList(name=name)
        patterns = {
            "Open": ["[please] (open|launch|start|bring up|take me to) {targets:target}",
                     "{targets:target} (kholo|khol do|open karo|खोलो|खोल दो)"],
            "Focus": ["(focus|switch to|bring forward) {targets:target}"],
            "Minimize": ["minimize {targets:target}"],
            "Maximize": ["maximize {targets:target}"],
            "Restore": ["restore {targets:target}"],
            "Close": ["close {targets:target}"],
            "Read": ["(read|show) [the] {filename} [file]"],
            "Save": ["(save|write) [a] {filename} [file]"],
            "Send": ["(send|upload|share) {artifact} (to|on) {destination}"],
            "Reason": ["(review|analyze|analyse|compare|explain) {subject}",
                       "(write|draft) [a] (spec|specification) for {subject}",
                       "what is {subject}", "why {subject}",
                       "{subject} क्या है", "{subject} kya hai", "{subject} samjhao"],
        }
        self.rules = Intents.from_dict({"language": "en", "intents": {
            name: {"data": [{"sentences": sentences}]} for name, sentences in patterns.items()
        }})

    def _matches(self, text: str) -> list[Action]:
        if re.match(r'(?:write|save|read|show)\b',text,re.I):
            text=text.rstrip('.!? ')
        spoken = re.fullmatch(r'(?:write|save) (.+?) (?:to|as) ([\w .-]+(?:\.\w+| dot (?:m d|md|txt|csv|json)))', text.strip(), re.I | re.S)
        if spoken:
            filename=re.sub(r'\s+dot\s+', '.',spoken[2],flags=re.I)
            filename=re.sub(r'\.m d$', '.md',filename,flags=re.I)
            if re.fullmatch(r'[\w .-]+\.(?:md|txt|csv|json)',filename,re.I):
                import json
                content=spoken[1]
                if content.startswith('"') and content.endswith('"'):
                    try: content=json.loads(content)
                    except ValueError: content=content[1:-1]
                return [Action('file.write_text',{'text':content,'filename':filename})]
        named_file=re.fullmatch(r'(read|show|save|write) (?:the )?([\w .-]+?)(?: file)?',text.strip(),re.I)
        if named_file:
            filename=re.sub(r'\s+dot\s+', '.',named_file[2],flags=re.I)
            filename=re.sub(r'\.m d$', '.md',filename,flags=re.I)
            if re.fullmatch(r'[\w .-]+\.(?:md|txt|csv|json)',filename,re.I):
                return [Action('file.read' if named_file[1].casefold() in {'read','show'} else 'file.write_artifact',{'filename':filename})]
        literal = re.fullmatch(r'(?:write|save) "((?:[^"\\]|\\.)*)" (?:to|as) ([\w .-]+\.(?:md|txt|csv|json))', text.strip(), re.I | re.S)
        if literal:
            import json
            try: content = json.loads('"'+literal[1]+'"')
            except ValueError: content = literal[1]
            return [Action("file.write_text", {"text":content,"filename":literal[2]})]
        names = {"Open": "target.open", "Focus": "window.focus", "Minimize": "window.minimize",
                 "Maximize": "window.maximize", "Restore": "window.restore", "Close": "window.close",
                 "Read": "file.read", "Save": "file.write_artifact", "Send": "slack.send_file", "Reason": "reason.generate"}
        unique: dict[str, Action] = {}
        for match in recognize_all(normalize(text).strip(".!?। "), self.rules, slot_lists=self.slots):
            args = {name: str(entity.value) for name, entity in match.entities.items()}
            if match.intent.name in {"Read","Save"} and not re.fullmatch(r"[\w .-]+\.(?:md|txt|csv|json)", args["filename"]):
                continue
            action = Action(names[match.intent.name], args)
            if match.intent.name == "Reason":
                args["request"] = text
                args["kind"] = "review_pr" if text.casefold().startswith("review ") else "generate_content"
            unique[repr((action.capability, sorted(args.items())))] = action
        if not unique:
            try:
                resolved = self.websites.resolve(text)
            except ValueError:
                return []
            if resolved:
                return [Action(resolved[0], {"url": resolved[1]})]
        return list(unique.values())

    @staticmethod
    def _clauses(text: str) -> list[str]:
        clauses = [""]
        for index, part in enumerate(re.split(r'("(?:[^"\\]|\\.)*")', text)):
            if index % 2:
                clauses[-1] += part
                continue
            pieces = re.split(r"\s+(?:and then|aur phir|then|phir|and|aur|और फिर|फिर|और)\s+|,\s+(?=(?:open|launch|read|write|save|send|search)\b)", part, flags=re.I)
            clauses[-1] += pieces[0]
            clauses.extend(pieces[1:])
        return [clause.strip() for clause in clauses if clause.strip()]

    def route(self, text: str) -> Intent:
        cleaned = normalize(text).strip(".!?। ")
        lang = language_of(text, self.language)
        if cleaned in {"stop", "wait", "ruk", "ruko", "रुको", "रुक"}:
            return Intent("stop", {}, 1.0, lang)
        if cleaned in {"help", "what can you open", "what can you do"}:
            return Intent("capabilities", {}, 1, lang)
        whole = self._matches(text.strip())
        if len(whole) == 1 and whole[0].capability == "target.open":
            return Intent("open_app", {"app": whole[0].args["target"]}, 1, lang, tuple(whole))
        if len(whole)==1 and whole[0].capability in {"file.write_text","file.read","file.write_artifact","web.search","website.open","browser.navigate"}:
            return Intent("routine",{},1,lang,tuple(whole))
        if len(whole)>1 and all(a.capability=="target.open" for a in whole):
            options=tuple(dict.fromkeys(a.args["target"] for a in whole))
            return Intent("clarify", {"reason":"ambiguous_target","suggestions":", ".join(options)},0,lang,(),options)
        actions: list[Action] = []
        for clause in self._clauses(text.strip()):
            matches = self._matches(clause)
            if len(matches) != 1:
                slots = {"reason": "unknown_or_ambiguous"}
                target = re.fullmatch(r"(?:open|launch|start) (.+)", clause)
                if target:
                    proposals = get_close_matches(target[1], self.aliases, n=3, cutoff=0.78)
                    names = list(dict.fromkeys(self.aliases[alias] for alias in proposals))
                    if names:
                        slots["suggestions"] = ", ".join(names)
                return Intent("clarify", slots, 0, lang)
            actions.append(matches[0])
        if not actions:
            return Intent("clarify", {"reason": "empty"}, 0, lang)
        kind = "reason" if len(actions) == 1 and actions[0].capability == "reason.generate" else "routine"
        return Intent(kind, {}, 1, lang, tuple(actions))
