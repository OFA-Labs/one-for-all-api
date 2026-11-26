"""The existing companion Session with OFA as its brain: same states and panel, OFA reasoning and approvals."""
import asyncio
import time

import pytest

from ofa.companion import OfaBrain, sentences
from ofa.config import OfaConfig
from ofa.egress import EGRESS
from ofa.engine.fake import FakeEngine, tool
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.runtime import build_core
from voice.config import Settings
from voice.contracts import Transcript
from voice.intent import Router
from voice.session import Session
from voice.state import State


class Yes:
    def verify(self, reason):
        return True


class Devices:
    epoch = 0

    def start(self): pass
    def close(self): pass
    def interrupt(self): return 0
    def mark(self, *_): pass


class Speech:
    def __init__(self): self.said = []

    async def say(self, text, language, playback, started):
        started()
        self.said.append(text)
        return True


class Stt:
    def __init__(self): self.next = []

    async def transcribe(self, feed):
        yield Transcript(self.next.pop(0), True, 0.97)


class Bridge:
    pending = None

    def __init__(self): self.opened = []
    async def open(self, name, command_id):
        self.opened.append(name)
        return True
    def stop(self): pass
    def resume(self): pass


class Cache:
    def get(self, language): raise KeyError(language)


@pytest.fixture
def rig(tmp_path, monkeypatch):
    monkeypatch.setenv("OFA_DATA_DIR", str(tmp_path))
    desk = FakeDesktop()
    engine = FakeEngine()
    core = build_core(OfaConfig(engine="fake"), harness=Harness(desk), engine=engine, verifier=Yes())
    core.approvals.echo_gap = 0.0
    brain = OfaBrain(core)
    events, captions = [], []
    speech, stt, bridge = Speech(), Stt(), Bridge()
    session = Session(Settings(), Router({"notepad": "Notepad"}), stt, speech, None, bridge, Cache(),
                      lambda kind, payload: events.append((kind, payload)), brain=brain)
    session.capture = session.playback = Devices()
    brain.attach(session, caption=lambda state, text="": captions.append((state, text)))
    yield type("Rig", (), dict(desk=desk, engine=engine, core=core, brain=brain, session=session, speech=speech,
                               stt=stt, bridge=bridge, events=events, captions=captions))
    EGRESS.forget_all()


def arm(session):
    session.state(State.ARMED)
    session.state(State.LISTENING)


async def hear(rig, text):
    """One microphone utterance, routed the way the capture loop routes it."""
    rig.stt.next.append(text)
    rig.session._utterance_started = time.monotonic()
    task = asyncio.create_task(rig.session._respond(object()))
    if rig.session._deciding():
        rig.session.decision_response = task
    else:
        rig.session.response = task
    return task


async def until(predicate, timeout=3.0):
    end = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < end, "condition not reached"
        await asyncio.sleep(0.01)


def test_unknown_request_goes_to_ofa_and_reply_is_spoken(rig):
    rig.engine.script = [[tool("finish", status="done", summary="It is Thursday")]]

    async def run():
        arm(rig.session)
        await (await hear(rig, "what day is it today"))
        assert len(rig.engine.requests) == 1
        assert any("It is Thursday" in s for s in rig.speech.said)
        assert rig.session.machine.state == State.LISTENING
    asyncio.run(run())


def test_plain_open_command_stays_on_the_verified_fast_path(rig):
    async def run():
        arm(rig.session)
        await (await hear(rig, "open notepad"))
        assert rig.bridge.opened == ["Notepad"] and rig.engine.requests == []
    asyncio.run(run())


def chat(desk):
    desk.add_window("Asha - WhatsApp", "whatsapp.exe", [("Type a message", "edit", (0, 0, 10, 10)),
                                                         ("Send", "button", (20, 0, 30, 10))])
    desk.on_click["Send"] = lambda d: d.elements[d.fg].clear()


SEND = [[tool("screen")], [tool("act", kind="click", element="u1", effect="send", to=["Asha"])],
        [tool("finish", status="done", summary="Sent to Asha")]]


def test_spoken_yes_reaches_the_pending_approval_without_cancelling_the_task(rig):
    rig.engine.script = list(SEND)
    chat(rig.desk)

    async def run():
        arm(rig.session)
        task = await hear(rig, "send it to Asha")
        await until(lambda: rig.brain.waiting)
        assert rig.session.machine.state == State.LISTENING          # microphone open for the answer
        await rig.session.interrupt()                                 # speech onset must not kill the task
        await (await hear(rig, "haan bhej do"))
        await task
        assert "Send" in rig.desk.clicks
        assert any(k == "question" and "Asha" in p["text"] for k, p in rig.events)
        assert any("Say yes or no" in text for _, text in rig.captions)
    asyncio.run(run())


def test_typed_yes_cannot_approve(rig):
    rig.engine.script = list(SEND)
    chat(rig.desk)
    rig.core.approvals.window = 0.1

    async def run():
        arm(rig.session)
        task = await hear(rig, "send it to Asha")
        await until(lambda: rig.brain.waiting)
        await rig.session.submit_text("yes")
        await task
        assert "Send" not in rig.desk.clicks
    asyncio.run(run())


def test_spoken_stop_kills_the_session_and_voids_the_approval(rig):
    rig.engine.script = list(SEND)
    chat(rig.desk)

    async def run():
        arm(rig.session)
        await hear(rig, "send it to Asha")
        await until(lambda: rig.brain.waiting)
        epoch = rig.core.epoch_ref[0]
        await (await hear(rig, "stop"))
        assert rig.session.machine.state == State.IDLE and rig.core.epoch_ref[0] > epoch
        assert "Send" not in rig.desk.clicks and not rig.brain.waiting
    asyncio.run(run())


def test_a_new_instruction_replaces_the_running_task(rig):
    gate = asyncio.Event()

    async def run():
        seen = []

        async def turn(text, confidence=None):
            seen.append(text)
            rig.brain.busy = True
            try:
                await gate.wait()
                return "done"
            finally:
                rig.brain.busy = False
        rig.brain.turn = turn
        arm(rig.session)
        first = await hear(rig, "find me a flat")
        await until(lambda: rig.brain.busy)
        second = await hear(rig, "no, search for jobs instead")
        await until(lambda: len(seen) == 2)
        assert first.cancelled() or first.done()
        assert rig.session.response is second and rig.session.decision_response is None
        gate.set()
        await second
    asyncio.run(run())


def test_own_voice_is_dropped(rig):
    async def run():
        arm(rig.session)
        await rig.brain.speak("Completed. Anything else?")
        await (await hear(rig, "completed anything else"))
        assert rig.engine.requests == []
    asyncio.run(run())


def test_pause_and_resume_hold_the_next_action(rig):
    async def run():
        arm(rig.session)
        await (await hear(rig, "pause"))
        assert not rig.brain.paused.is_set()
        await (await hear(rig, "continue"))
        assert rig.brain.paused.is_set() and rig.engine.requests == []
    asyncio.run(run())


def test_without_a_brain_the_companion_behaves_as_before():
    session = Session(Settings(), Router({}), None, None, None, Bridge(), None, lambda *_: None)
    assert session.brain is None and not session._deciding()


def test_long_replies_are_spoken_in_sentence_chunks():
    text = " ".join(f"Step {i} is to do the thing carefully." for i in range(30))
    parts = sentences(text)
    assert len(parts) > 3 and all(len(p) <= 280 for p in parts) and " ".join(parts) == text
