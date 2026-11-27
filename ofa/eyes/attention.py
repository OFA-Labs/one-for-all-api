"""Notices windows that appear on their own (an incoming call, a notification, a dialog).

It runs while the companion runs, because a call usually rings before Caps Lock is pressed. It only lists
windows (no screenshots, nothing leaves the laptop). The newest pop-up is kept in memory.context["latest_popup"]
so a request like "pick it up" can refer to it.
"""
from __future__ import annotations

import asyncio
import logging
import time

from ..harness.api import Harness
from ..memory import Memory

log = logging.getLogger("ofa.eyes")
INTERVAL = 1.0
FRESH_SECONDS = 90           # older pop-ups are not offered as "it"
OWN = {"OFA", "OFA Desktop"}


class Attention:
    def __init__(self, harness: Harness, memory: Memory):
        self.h, self.memory = harness, memory
        self._known: set[int] | None = None
        self._task: asyncio.Task | None = None

    def poll(self) -> dict | None:
        """One check: record and return the newest window that was not there last time."""
        wins = self.h.b.list_windows()
        current = {w["hwnd"] for w in wins}
        if self._known is None:
            self._known = current
            return None
        new = [w for w in wins if w["hwnd"] not in self._known and w["title"] not in OWN and not w["minimized"]]
        self._known = current
        if not new:
            return None
        w = new[0]
        popup = {"hwnd": w["hwnd"], "title": w["title"][:80], "app": w["process"].removesuffix(".exe"),
                 "rect": list(w["rect"]), "at": time.time()}
        self.memory.context["latest_popup"] = popup
        return popup

    def latest(self) -> dict | None:
        popup = self.memory.context.get("latest_popup")
        if popup and time.time() - popup["at"] <= FRESH_SECONDS and popup["hwnd"] in {
                w["hwnd"] for w in self.h.b.list_windows()}:
            return popup
        return None

    def start(self) -> None:
        """Start polling on the running event loop (the companion's); without one there is nothing to watch."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        if self._task is None:
            self._task = loop.create_task(self._run())

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.poll)
            except Exception:
                log.debug("attention poll failed", exc_info=True)
            await asyncio.sleep(INTERVAL)
