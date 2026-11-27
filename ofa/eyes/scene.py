"""What OFA can see right now: elements of the visible windows, each with a numbered mark (m1, m2, …).

Accessibility (UIA) first: it is free, exact and names controls. OCR fills in only windows that expose
little text (Electron apps such as WhatsApp, Slack, VS Code). Elements hidden behind a window that is
higher in the stacking order are left out, so a mark is always something the user could click.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..harness.api import Harness, HarnessError, Snapshot, norm
from ..harness.win import El

MAX_WINDOWS = 8          # windows read for the whole screen, top of the stack first
MAX_MARKS = 150
OCR_BELOW = 8            # a window with fewer text elements than this also gets OCR
INTERACTIVE = {"button", "edit", "hyperlink", "link", "list item", "menu item", "tab item", "check box",
               "combo box", "radio button", "tree item", "document", "split button", "toggle button"}


@dataclass
class Scene:
    marks: list[El]
    windows: list[dict]
    sources: list[str]
    origin: tuple[int, int, int, int]          # the screen area the marks cover
    at: float = field(default_factory=time.monotonic)

    def mark(self, mid: str) -> El | None:
        return next((m for m in self.marks if m.id == mid), None)

    def public(self, limit: int = 70) -> list[str]:
        titles = {w["hwnd"]: w["title"][:40] for w in self.windows}
        return [f"{m.public()} @{titles.get(m.hwnd, '')}" for m in self.marks[:limit]]

    def text_count(self) -> int:
        return sum(1 for m in self.marks if m.text or m.value)


def _covered(point: tuple[int, int], above: list[tuple[int, int, int, int]]) -> bool:
    x, y = point
    return any(l <= x < r and t <= y < b for l, t, r, b in above)


def _rank(e: El) -> tuple:
    return (0 if e.role in INTERACTIVE else 1, e.bbox[1], e.bbox[0])


def build_scene(h: Harness, scope: str = "screen", window=None, ocr: bool = False) -> Scene:
    """Read the screen (or one window) and give every element a mark. `ocr` adds OCR to text-poor windows."""
    if scope == "window" or window:
        wins = [h.resolve_window(window)]
    else:
        fg = h.b.foreground()
        wins = [w for w in h.b.list_windows() if not w["minimized"]]
        wins.sort(key=lambda w: w["hwnd"] != fg)           # the front window first, then stacking order
        wins = wins[:MAX_WINDOWS]
    if not wins:
        raise HarnessError("NO_WINDOW", "No window is open")
    marks: list[El] = []
    above: list[tuple[int, int, int, int]] = []
    sources = {"uia"}
    for w in wins:
        l, t, r, b = w["rect"]
        if above and all(_covered(p, above) for p in ((l + 8, t + 8), (r - 8, t + 8), (l + 8, b - 8), (r - 8, b - 8),
                                                     ((l + r) // 2, (t + b) // 2))):
            continue                                   # fully behind other windows: nothing to see or click
        try:
            els, _ = h.b.uia_tree(w["hwnd"], max_nodes=700, budget_s=0.8)
        except Exception:
            els = []
        texty = [e for e in els if e.text or e.value]
        if ocr and len(texty) < OCR_BELOW:
            try:
                bgra, width, height = h.b.capture(w["rect"])
                known = {norm(e.text) for e in els}
                els += [e for e in h.b.ocr(bgra, width, height, (w["rect"][0], w["rect"][1])) if norm(e.text) not in known]
                sources.add("ocr")
            except Exception:
                pass
        for e in sorted(els, key=_rank):
            l, t, r, b = e.bbox
            if r - l < 3 or b - t < 3 or not (e.text or e.value or e.role in INTERACTIVE):
                continue
            if _covered(e.center(), above):
                continue
            e.hwnd = w["hwnd"]
            if (w["hwnd"], e.id) in h.filled_refs or e.is_password:
                e.value = None
            marks.append(e)
        above.append(w["rect"])
    marks = marks[:MAX_MARKS]
    for i, e in enumerate(marks, 1):
        e.id = f"m{i}"
    front = wins[0]
    area = front["rect"] if scope == "window" or window else h.b.virtual_screen()
    # Hands act on the latest reading: from here, act(element="m12") clicks this mark.
    h.last = Snapshot(front["hwnd"], front["title"], front["process"], marks, True, tuple(sorted(sources)),
                      time.monotonic())
    return Scene(marks, [{"hwnd": w["hwnd"], "title": w["title"], "app": w["process"].removesuffix(".exe")}
                         for w in wins], sorted(sources), area)
