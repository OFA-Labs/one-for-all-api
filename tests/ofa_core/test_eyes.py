"""Eyes: cheapest reading first, the user's chosen provider last, masked images, marks the hands can act on."""
import asyncio
import json
import time

import numpy as np
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from ofa.audit import Audit
from ofa.engine.base import RedactedImage, TextDelta
from ofa.engine.fake import FakeEngine, tool
from ofa.eyes import Eyes
from ofa.eyes.attention import Attention
from ofa.eyes.capture import look_image
from ofa.eyes.providers import ModelEyes
from ofa.eyes.scene import build_scene
from ofa.graphs import Runner
from ofa.graphs.deps import Deps
from ofa.graphs.eyes import eyes_graph
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.harness.win import El
from ofa.memory import Memory
from ofa.policy import Action, ApprovalStore, TurnLog, classify_tier
from ofa.ports import VoicePort
from ofa.settings_store import SettingsStore


class VisionEngine:
    """Stands in for a vision model: records what it was shown, answers with a fixed JSON reply."""

    def __init__(self, reply: dict, sees=True):
        self.reply, self.sees, self.images = reply, sees, []

    def info(self):
        return FakeEngine(vision=self.sees).info()

    async def stream(self, messages, tools, *, images=()):
        self.images.extend(images)
        yield TextDelta(json.dumps(self.reply))


def make(tmp_path, mode="local", engine=None, elements=(("Apply", "button", (20, 100, 120, 135)),)):
    desk = FakeDesktop()
    desk.add_window("OFA Execution Test Pad", "python.exe", elements)
    desk.wins[desk.fg]["rect"] = (0, 0, 800, 600)
    settings = SettingsStore(None)
    settings.update({"eyes": {"mode": mode}})
    voice = VoicePort()
    deps = Deps(Harness(desk), ApprovalStore(), TurnLog(), Audit(tmp_path / "audit"), Memory(tmp_path / "m.db"),
                None, engine or FakeEngine(), voice, lambda: 0, settings=settings)
    return deps, desk


def look(deps, question="", call_id="c1"):
    graph = eyes_graph(deps).compile(checkpointer=InMemorySaver())
    call = {"id": call_id, "name": "look", "args_json": json.dumps({"question": question})}
    out = asyncio.run(graph.ainvoke({"call": call}, {"configurable": {"thread_id": call_id}}))
    return out["tool_out"]


def test_accessibility_answers_first_and_nothing_is_captured(tmp_path, monkeypatch):
    deps, desk = make(tmp_path, mode="separate")
    monkeypatch.setattr("ofa.graphs.eyes.look_image", lambda *a: pytest.fail("no screenshot needed"))
    out = look(deps, "the Apply button")
    assert out["seen_by"] == "accessibility" and out["sight"]["mark"] == "m1"
    assert any(line.startswith('m1 button "Apply"') for line in out["marks"])


def test_ocr_reads_text_poor_windows(tmp_path):
    deps, desk = make(tmp_path, elements=())
    desk.ocr_lines = [El("o0", "Accept", "text", (300, 200, 360, 220), "ocr")]
    out = look(deps, "Accept")
    assert out["sight"]["mark"] == "m1" and "ocr" in out["seen_by"]


def test_local_mode_never_sends_an_image(tmp_path, monkeypatch):
    deps, _ = make(tmp_path, mode="local", elements=(("Toolbar", "pane", (0, 0, 800, 40)),))
    monkeypatch.setattr("ofa.graphs.eyes.look_image", lambda *a: pytest.fail("local mode must not capture"))
    out = look(deps, "the green phone icon")
    assert set(out["seen_by"].split("+")) == {"ocr", "uia"} and "mark" not in out["sight"]


def test_separate_model_gets_a_masked_marked_image_and_points_are_scaled(tmp_path):
    deps, desk = make(tmp_path, mode="separate", elements=(("Password", "edit", (10, 10, 200, 40)),))
    desk.elements[desk.fg][0].is_password = True
    eyes_model = VisionEngine({"answer": "The green phone icon", "point": [100, 50], "label": "Accept call",
                               "confidence": 0.8})
    deps.eyes._separate[deps.settings.get().eyes.model] = ModelEyes(eyes_model, "separate")
    out = look(deps, "the green phone icon")
    assert out["seen_by"].endswith("separate")
    assert isinstance(eyes_model.images[0], RedactedImage) and "1 regions masked" in eyes_model.images[0].note
    step = -(-1920 // 1600)
    assert out["sight"]["point"] == [100 * step, 50 * step] and out["sight"]["label"] == "Accept call"
    assert deps.harness.last_sight["label"] == "Accept call"


def test_reasoning_mode_uses_the_engine_only_when_it_can_see(tmp_path):
    blind, _ = make(tmp_path, mode="reasoning", engine=VisionEngine({}, sees=False))
    assert blind.eyes.provider().name == "local" and blind.eyes.status()["note"]
    seeing_engine = VisionEngine({"answer": "Apply", "mark": "m1", "confidence": 0.95})
    seeing, _ = make(tmp_path, mode="reasoning", engine=seeing_engine)
    assert seeing.eyes.provider().name == "reasoning"
    out = look(seeing, "the thing that saves my changes")
    assert out["sight"]["mark"] == "m1" and seeing_engine.images


def test_marks_are_drawn_and_hidden_elements_skipped(tmp_path):
    deps, desk = make(tmp_path)
    back = desk.add_window("Back", "back.exe", [("Hidden", "button", (50, 110, 90, 130))])
    desk.fg = 100                                     # the test pad stays in front and covers "Hidden"
    desk.wins[back]["rect"] = (0, 0, 800, 600)
    scene = build_scene(deps.harness)
    assert [m.text for m in scene.marks] == ["Apply"]
    desk.to_png = lambda bgra, w, h: bytes(bgra)        # compare the pixels themselves
    image, _ = look_image(deps.harness, scene)
    plain, _ = look_image(deps.harness, scene, marked=False)
    assert image.png != plain.png


def test_unlabelled_screen_points_need_a_spoken_yes():
    plain = Action(verb="click", args={"op": "click", "x": 10, "y": 10})
    named = plain.model_copy(update={"element_label": "Volume"})
    assert classify_tier(plain) == 2 and classify_tier(named) == 1


def test_act_on_a_mark_from_look(tmp_path):
    deps, desk = make(tmp_path, elements=(("Bold", "button", (20, 100, 120, 135)),))
    clicked = []
    desk.on_click["Bold"] = lambda d: clicked.append(True) or d.elements[d.fg].append(El("u9", "Done", "text", (0, 0, 5, 5)))
    deps.engine.script = [[tool("look", question="Bold")], [tool("act", kind="click", element="m1")],
                          [tool("finish", status="done", summary="Made it bold")]]
    result = asyncio.run(Runner(deps).handle("press bold on the test pad"))
    assert clicked and result.status == "done"


def test_attention_notices_a_call_window_and_the_brain_is_told(tmp_path):
    deps, desk = make(tmp_path)
    watcher = Attention(deps.harness, deps.memory)
    deps.attention = watcher
    watcher.poll()
    desk.add_window("WhatsApp", "whatsapp.exe", [("Accept", "button", (900, 500, 960, 540))])
    assert watcher.poll()["app"] == "whatsapp"
    deps.engine.script = [[tool("finish", status="done", summary="ok")]]
    asyncio.run(Runner(deps).handle("pick it up"))
    user = deps.engine.requests[0]["messages"][-1]["content"]
    assert "a new window appeared" in user and "WhatsApp" in user
    deps.memory.context["latest_popup"]["at"] = time.time() - 600
    assert watcher.latest() is None


def test_settings_store_validates_and_persists(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    store.update({"eyes": {"mode": "separate", "model": "qwen/qwen3.8-27b"}})
    assert SettingsStore(tmp_path / "settings.json").get().eyes.mode == "separate"
    with pytest.raises(Exception):
        store.update({"eyes": {"mode": "telepathy"}})
    with pytest.raises(ValueError):
        store.update({"brain": {}})
    assert np is not None
