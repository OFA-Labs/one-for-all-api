"""Runs the turn graph for the voice front end and answers its interrupts.

Each task is one checkpointed thread. When a node pauses with a Question, drive() speaks it, listens, and
resumes the thread with Command(resume=Answer). A thread that finished is deleted from the checkpoint store.
At most one unfinished thread is kept, so "continue the last task" can start it again, also after a restart.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from .deps import Deps
from .pauses import heard_dict
from .report import TurnResult
from .turn import turn_graph

log = logging.getLogger("ofa.graphs")
RECURSION_LIMIT = 600            # supersteps per task: 25 engine steps × a few nodes per tool call


class CallbackIO:
    """Plain speak/listen callables as a voice front end (tests, typed tools)."""

    def __init__(self, speak, listen, listen_dictation=None):
        self.speak, self.listen = speak, listen
        self.listen_dictation = listen_dictation or listen


async def drive(graph, payload, config: dict, io, stopped=lambda: False) -> dict | None:
    """Invoke until the graph ends. Returns its final state, or None when the session stopped meanwhile."""
    config = {"recursion_limit": RECURSION_LIMIT, **config}
    current = payload
    while True:
        out = await graph.ainvoke(current, config)
        paused = out.get("__interrupt__") if isinstance(out, dict) else None
        if not paused:
            return out
        question = paused[0].value
        tts_end = await io.speak(question["say"]) if question["say"] else time.monotonic()
        started = time.monotonic()
        listen = io.listen_dictation if question.get("mode") == "dictation" else io.listen
        heard = await listen(question["timeout"])
        if stopped():
            return None
        current = Command(resume={"heard": heard_dict(heard), "tts_end": tts_end, "listen_started": started})


class Runner:
    def __init__(self, deps: Deps, db_path: Path | None = None):
        self.deps, self.db_path = deps, db_path
        self._graph = None
        self._loop = None

    async def graph(self):
        """Compiled once per event loop: the SQLite connection belongs to the loop that opened it."""
        loop = asyncio.get_running_loop()
        if self._graph is None or self._loop is not loop:
            saver = InMemorySaver()
            if self.db_path is not None:
                import aiosqlite
                from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
                saver = AsyncSqliteSaver(await aiosqlite.connect(str(self.db_path)))
            self._graph, self._loop = turn_graph(self.deps).compile(checkpointer=saver), loop
        return self._graph

    async def aclose(self) -> None:
        """Close the SQLite connection; its worker thread would otherwise keep the process alive."""
        conn = getattr(getattr(self._graph, "checkpointer", None), "conn", None)
        if conn is not None:
            await conn.close()
        self._graph = self._loop = None

    def _config(self, thread: str) -> dict:
        return {"configurable": {"thread_id": thread}}

    @property
    def last_thread(self) -> str | None:
        """The unfinished task, remembered on this computer so it survives a restart."""
        return self.deps.memory.get("last_thread")

    async def handle(self, text: str, confidence: float | None = None) -> TurnResult:
        await self._forget(self.last_thread)
        thread = f"{self.deps.epoch()}-{uuid4().hex[:10]}"
        self.deps.memory.set("last_thread", thread)
        return await self._run({"text": text, "confidence": confidence}, thread)

    async def resume_last(self) -> TurnResult | None:
        """Start the stopped task again from the user's own words; None when there is nothing to continue.

        A stop voids the old session, including any approval given in it, so the task is not replayed from the
        middle: it reads the screen afresh, asks again before anything consequential, and the action ledger
        still refuses to repeat a send it knows succeeded.
        """
        thread = self.last_thread
        if not thread:
            return None
        graph = await self.graph()
        snapshot = await graph.aget_state(self._config(thread))
        text = snapshot.values.get("text")
        if not snapshot.next or not text:
            return None
        return await self.handle(text, snapshot.values.get("confidence"))

    async def _forget(self, thread: str | None) -> None:
        if not thread:
            return
        try:
            await (await self.graph()).checkpointer.adelete_thread(thread)
        except Exception:
            log.debug("could not delete thread", exc_info=True)

    async def _run(self, payload, thread: str) -> TurnResult:
        graph, epoch = await self.graph(), self.deps.epoch()
        out = await drive(graph, payload, self._config(thread), self.deps.voice, lambda: self.deps.epoch() != epoch)
        if out is None or not out.get("result"):
            return TurnResult("", "cancelled")
        await self._forget(thread)                     # finished: keep no conversation on disk
        if self.last_thread == thread:
            self.deps.memory.set("last_thread", None)
        return TurnResult(**out["result"])
