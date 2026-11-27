"""Saved progress: a paused task survives a stop, resumes safely, and a finished task leaves nothing on disk."""
import asyncio
import time

from ofa.audit import Audit
from ofa.engine.fake import FakeEngine, tool
from ofa.graphs import Runner
from ofa.graphs.deps import Deps
from ofa.graphs.turn import turn_graph
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.memory import Memory
from ofa.policy import ApprovalStore, TurnLog
from ofa.policy.approval import Heard
from ofa.ports import VoicePort

SEND = [[tool("screen")], [tool("act", kind="click", element="u1", effect="send", to=["Asha"])],
        [tool("finish", status="done", summary="Sent to Asha")]]


def rig(tmp_path, answers, db=False):
    desk = FakeDesktop()
    desk.add_window("Asha - WhatsApp", "whatsapp.exe", [("Type a message", "edit", (0, 0, 10, 10)),
                                                         ("Send", "button", (20, 0, 30, 10))])
    desk.on_click["Send"] = lambda d: d.elements[d.fg].clear()      # the sent message leaves the compose box
    epoch, spoken = [0], []

    async def speak(text):
        spoken.append(text)
        return time.monotonic() - 5

    async def listen(_):
        await asyncio.sleep(0)
        nxt = answers.pop(0) if answers else None
        return nxt(epoch) if callable(nxt) else nxt
    voice = VoicePort()
    voice.attach(speak=speak, listen=listen)
    approvals = ApprovalStore()
    deps = Deps(Harness(desk), approvals, TurnLog(), Audit(tmp_path / "audit"), Memory(tmp_path / "m.db"), None,
                FakeEngine(list(SEND)), voice, lambda: epoch[0])
    return Runner(deps, tmp_path / "graphs.db" if db else None), desk, epoch, spoken


def _answers(*heard):
    queue = list(heard)

    async def listen(_):
        await asyncio.sleep(0)
        return queue.pop(0) if queue else None
    return listen


def test_a_stopped_task_continues_after_a_restart_and_asks_again(tmp_path):
    def stop_session(epoch):
        epoch[0] += 1                      # Caps Lock: the kill switch bumps the epoch
        return None
    runner, desk, epoch, spoken = rig(tmp_path, [stop_session], db=True)

    async def run():
        first = await runner.handle("send it to Asha")
        assert first.status == "cancelled" and runner.last_thread and "Send" not in desk.clicks
        await runner.aclose()
        restarted = Runner(runner.deps, tmp_path / "graphs.db")       # a new process, same disk
        runner.deps.engine.script = list(SEND)
        runner.deps.approvals.set_epoch(epoch[0])
        runner.deps.voice._listen = _answers(Heard("haan bhej do"))
        try:
            return await restarted.resume_last(), restarted.last_thread
        finally:
            await restarted.aclose()
    resumed, left = asyncio.run(run())
    assert resumed.status == "done" and desk.clicks.count("Send") == 1 and left is None
    assert sum(s.startswith("I'm about to send") for s in spoken) == 2


def test_finished_task_is_deleted_from_the_checkpoint_store(tmp_path):
    runner, desk, _, _ = rig(tmp_path, [Heard("haan bhej do")], db=True)

    async def run():
        try:
            result = await runner.handle("send it to Asha")
            graph = await runner.graph()
            threads = [c async for c in graph.checkpointer.alist(None)]
            return result, threads, await runner.resume_last()
        finally:
            await runner.aclose()
    result, threads, again = asyncio.run(run())
    assert result.status == "done" and desk.clicks.count("Send") == 1
    assert threads == [] and runner.last_thread is None and again is None


def test_graph_shows_every_part(tmp_path):
    runner, *_ = rig(tmp_path, [])
    diagram = turn_graph(runner.deps).compile().get_graph(xray=True).draw_mermaid()
    for node in ("route", "decide", "after_tool", "classify", "approved", "effect", "listen", "dictation_listen"):
        assert node in diagram
