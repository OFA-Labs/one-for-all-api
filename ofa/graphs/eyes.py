"""Eyes subgraph: answer "what is on screen / where is X" as cheaply as possible.

    read (accessibility) ─(sure)─▶ END
         └─▶ ocr (text-poor windows) ─(sure, or Local mode)─▶ END
                  └─▶ vision (the provider chosen in Settings → Eyes) ─▶ END

Reading is Tier 0: it changes nothing. A screenshot leaves the laptop only in the vision step, only in the
Separate or Reasoning modes, and only with password and vault-filled fields blacked out.
"""
from __future__ import annotations

import asyncio
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from ..eyes.capture import look_image
from ..eyes.providers import Sight
from ..eyes.scene import OCR_BELOW, Scene, build_scene
from ..harness.api import HarnessError
from ..tools import ToolArgError, parse_args
from .deps import Deps
from .state import jsonable

SURE = 0.9


class EyesState(TypedDict, total=False):
    call: dict
    tool_out: dict | None
    action_info: dict | None
    look: dict
    route: str


def eyes_graph(deps: Deps) -> StateGraph:
    scenes: dict[str, Scene] = {}          # live scene per look; El objects cannot go into a checkpoint

    def sure(sight: Sight) -> bool:
        return sight.mark is not None and sight.confidence >= SURE

    def done(s: EyesState, scene: Scene, sight: Sight, seen_by: str) -> dict:
        scenes.pop(s["call"]["id"], None)
        deps.harness.last_sight = {"mark": sight.mark, "point": sight.point, "label": sight.label}
        out = {"status": "ok", "seen_by": seen_by, "windows": [w["title"][:60] for w in scene.windows],
               "sight": sight.public(), "marks": scene.public(60), "more_marks": max(0, len(scene.marks) - 60),
               "how_to_act": "act(kind=click, element=<mark>) or, for an unmarked icon, act(kind=click, x, y)"}
        return {"tool_out": jsonable(out), "action_info": None, "route": "end"}

    async def scan(s: EyesState, ocr: bool) -> Scene:
        look = s["look"]
        scene = await asyncio.to_thread(build_scene, deps.harness, look["scope"], look.get("window"), ocr)
        scenes[s["call"]["id"]] = scene
        return scene

    async def read(s: EyesState) -> dict:
        try:
            args = parse_args(s["call"]["args_json"])
        except ToolArgError as exc:
            return {"tool_out": {"status": "error", "reason": "BAD_ARGS", "detail": str(exc)}, "route": "end"}
        whole = deps.settings.get().eyes.whole_screen if deps.settings else True
        scope = args.get("scope") or "screen"
        look = {"question": str(args.get("question") or "")[:300], "window": args.get("window"),
                "scope": "screen" if scope == "screen" and whole and not args.get("window") else "window"}
        deps.voice.display("acting", "Looking at your screen")
        s = {**s, "look": look}
        try:
            scene = await scan(s, ocr=False)
        except HarnessError as exc:
            return {"tool_out": {"status": "error", "reason": exc.code, "detail": str(exc)}, "route": "end"}
        sight = deps.eyes.local.look(look["question"], scene)
        if sure(sight) or (not look["question"] and scene.text_count() >= OCR_BELOW):
            return {"look": look, **done(s, scene, sight, "accessibility")}
        return {"look": look, "route": "ocr"}

    async def ocr(s: EyesState) -> dict:
        scene = await scan(s, ocr=True)
        sight = deps.eyes.local.look(s["look"]["question"], scene)
        provider = deps.eyes.provider()
        if sure(sight) or not provider.sees_images or not s["look"]["question"]:
            return done(s, scene, sight, "+".join(scene.sources))
        return {"route": "vision"}

    async def vision(s: EyesState) -> dict:
        scene = scenes.get(s["call"]["id"]) or await scan(s, ocr=True)
        provider = deps.eyes.provider()
        deps.voice.display("acting", "Looking closely at your screen")
        image, scale = await asyncio.to_thread(look_image, deps.harness, scene)
        sight = await provider.look(s["look"]["question"], scene, image, scale)
        return done(s, scene, sight, f"{'+'.join(scene.sources)}+{provider.name}")

    g = StateGraph(EyesState)
    for node in (read, ocr, vision):
        g.add_node(node.__name__, node)
    by_route = lambda s: END if s.get("route") == "end" else s["route"]
    g.add_edge(START, "read")
    g.add_conditional_edges("read", by_route, ["ocr", END])
    g.add_conditional_edges("ocr", by_route, ["vision", END])
    g.add_edge("vision", END)
    return g
