"""The "Use without consent" corpus: Markdown documents split into small facts.

Only the facts relevant to a question are sent to the model, which keeps requests small and fast.
"""
from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz

NAME = re.compile(r"^[a-z0-9][a-z0-9 _-]{0,60}$")
MAX_BYTES = 200_000
STOP = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "your", "you", "have", "with", "any", "if",
        "please", "what", "which", "are", "is", "do", "how", "mention", "briefly", "enter", "answer", "relevant"}


@dataclass(frozen=True)
class Fact:
    doc: str
    section: str          # heading path, e.g. "Experience › Machine Learning Intern"
    text: str

    def public(self) -> str:
        return f"[{self.doc} › {self.section}] {self.text}"


class OpenCorpus:
    def __init__(self, root: Path):
        self.root = root
        self._lock = threading.Lock()

    # --- documents (edited from the web page) ------------------------------------------------------
    def _path(self, name: str) -> Path:
        name = name.removesuffix(".md").strip().casefold()
        if not NAME.match(name):
            raise ValueError("Use letters, numbers, spaces, - or _ (at most 60)")
        return self.root / f"{name}.md"

    def list(self) -> list[dict]:
        if not self.root.exists():
            return []
        return [{"name": p.stem, "bytes": p.stat().st_size, "modified": p.stat().st_mtime}
                for p in sorted(self.root.glob("*.md"))]

    def read(self, name: str) -> str:
        return self._path(name).read_text(encoding="utf-8")

    def write(self, name: str, text: str) -> dict:
        if len(text.encode("utf-8")) > MAX_BYTES:
            raise ValueError("Document is too large (200 KB at most)")
        path = self._path(name)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(path)
        return {"name": path.stem, "bytes": path.stat().st_size}

    def append(self, name: str, heading: str, text: str) -> None:
        """Save an answer the user gave so it can be reused (offered after a form question)."""
        path = self._path(name)
        current = path.read_text(encoding="utf-8") if path.exists() else f"# {name.title()}\n"
        self.write(name, current.rstrip() + f"\n\n## {heading.strip()}\n{text.strip()}\n")

    def delete(self, name: str) -> bool:
        path = self._path(name)
        with self._lock:
            if path.exists():
                path.unlink()
                return True
        return False

    # --- facts (what the model sees) ---------------------------------------------------------------
    def facts(self) -> list[Fact]:
        out: list[Fact] = []
        for doc in self.list():
            heads: list[str] = []
            for block in re.split(r"\n\s*\n", self.read(doc["name"])):
                for line in block.strip().splitlines():
                    line = line.strip()
                    heading = re.match(r"^(#{1,6})\s+(.*)$", line)
                    if heading:
                        level = len(heading.group(1))
                        heads = heads[:level - 1] + [heading.group(2).strip()]
                        continue
                    text = re.sub(r"^[-*•]\s+", "", line)
                    if text:
                        out.append(Fact(doc["name"], " › ".join(heads[1:] or heads) or doc["name"], text))
        return out

    def sections(self) -> list[Fact]:
        """One entry per heading, with all its lines: a date or role never travels without what it belongs to."""
        grouped: dict[tuple[str, str], list[str]] = {}
        for f in self.facts():
            grouped.setdefault((f.doc, f.section), []).append(f.text)
        return [Fact(doc, section, " | ".join(lines)) for (doc, section), lines in grouped.items()]

    def relevant(self, questions: list[str], budget_chars: int = 9000) -> list[Fact]:
        """Whole sections for these questions within a size budget, best first. Identity sections always come."""
        sections = self.sections()
        if sum(len(f.public()) for f in sections) <= budget_chars:
            return sections
        words = {w for q in questions for w in re.findall(r"[a-z0-9]+", q.casefold()) if w not in STOP and len(w) > 2}
        query = " ".join(sorted(words))

        def score(f: Fact) -> float:
            heading, body = f.section.casefold(), f.text.casefold()
            hits = sum(3 if w in heading else 1 if w in body else 0 for w in words)
            always = 500 if heading in {"contact", "identity", "personal", "education"} else 0
            return hits * 20 + fuzz.token_set_ratio(query, f"{heading} {body}") / 5 + always
        picked, used = [], 0
        for f in sorted(sections, key=score, reverse=True):
            size = len(f.public()) + 1
            if used + size > budget_chars:
                continue
            picked.append(f)
            used += size
        return picked
