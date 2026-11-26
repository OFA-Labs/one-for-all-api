import asyncio
import threading
from types import SimpleNamespace

from voice.bridge import EngineBridge
from voice.intent import Router


def test_spoken_stop_always_stops_even_while_an_approval_is_pending():
    from voice.session import Session
    from voice.config import Settings
    from voice.contracts import Transcript
    from voice.state import State
    class Bridge:
        pending={'state':'approval'}
        stopped=False
        def stop(self): self.stopped=True
    class Stt:
        async def transcribe(self,feed): yield Transcript('stop',True,.99)
    async def run():
        bridge=Bridge()
        session=Session(Settings(),Router({}),Stt(),None,None,bridge,None,lambda *_:None)
        session.runtime=SimpleNamespace(decide_voice=lambda *_:pytest.fail('Stop must precede approval recognition'))
        session.state(State.ARMED); session.state(State.LISTENING)
        session.decision_response=asyncio.current_task()
        await session._respond(None)
        assert bridge.stopped and session.machine.state==State.IDLE
    import pytest
    asyncio.run(run())


def test_fuzzy_name_only_suggests_and_never_dispatches():
    intent = Router({"whatsapp": "WhatsApp"}).route("open whatsap")
    assert intent.intent == "clarify"
    assert intent.slots["suggestions"] == "WhatsApp"
    assert intent.actions == ()


def test_stop_cancels_a_queued_action_instead_of_replaying_on_resume():
    class Engine:
        def __init__(self): self.controls = []
        def submit(self, command_id, plan): return {"task_id": "pending"}
        def snapshot(self, task_id): return {"state": "queued", "events": []}
        def control(self, task_id, control): self.controls.append((task_id, control.action))
        def emergency_stop(self): self.controls.append((None, "stop"))
    async def run():
        engine = Engine()
        bridge = EngineBridge(engine)
        task = asyncio.create_task(bridge.open("WhatsApp", "command"))
        await asyncio.sleep(0.05)
        bridge.stop()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        bridge.resume()
        assert ("pending", "cancel") in engine.controls
        assert engine.controls.index(("pending", "cancel")) < engine.controls.index((None, "resume"))
    asyncio.run(run())


def test_cancellation_during_submission_waits_for_identity_and_cancels_it():
    entered, release = threading.Event(), threading.Event()
    class Engine:
        def __init__(self): self.controls = []
        def submit(self, command_id, plan):
            entered.set()
            assert release.wait(2)
            return {"task_id": "late"}
        def control(self, task_id, control): self.controls.append((task_id, control.action))
        def emergency_stop(self): self.controls.append((None, "stop"))
    async def run():
        engine = Engine()
        task = asyncio.create_task(EngineBridge(engine).open("WhatsApp", "command"))
        await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        release.set()
        await asyncio.gather(task, return_exceptions=True)
        assert ("late", "cancel") in engine.controls
    asyncio.run(run())
