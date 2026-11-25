"""EXPERIMENTAL voice bridge: a best-effort memory pack, off the turn's critical path.

The real voice agent imports :class:`EBrainPackClient` and inserts
``{"role": "system", "content": client.pack}`` after its own system message.
There is no model call here. A refresh only starts background work; the caller
never waits for the network, and an unreachable or unconfigured service leaves
``pack == ""`` so the voice agent simply runs without memory.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

import httpx

from .cli import DEFAULT_URL, REQUEST_TIMEOUT

# LIMIT: 1024 is the configured default_token_budget (08-config.md), not a
# measured voice latency or quality claim; the bundle is capped by the service.
DEFAULT_TOKEN_BUDGET = 1024
SESSION_QUERY = "one-for-all project decisions architecture constraints"


class EBrainPackClient:
    """EXPERIMENTAL: refresh a system-message pack without blocking a voice turn.

    # UNTESTED: freshness and usefulness of the pack in a real voice session are
    # | unproven; settle: T-082 extended with a labelled real-session audit.
    """

    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        *,
        query: str = SESSION_QUERY,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        client_factory: Any = None,
    ) -> None:
        # UNTESTED: the best session query and budget for a real conversation
        # | are unmeasured; settle: T-082 real-session comparison of queries.
        self.url = (url or os.getenv("EBRAIN_URL") or DEFAULT_URL).rstrip("/")
        self.token = token if token is not None else os.getenv("EBRAIN_AGENT_TOKEN", "")
        self.query = query
        self.token_budget = token_budget
        self._factory = client_factory or httpx.Client
        self._pack = ""
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None

    @property
    def pack(self) -> str:
        """The last rendered bundle; empty until a successful background refresh."""
        with self._lock:
            return self._pack

    def refresh(self, query: str | None = None) -> None:
        """EXPERIMENTAL: schedule a background refresh; never call HTTP inline.

        # UNTESTED: overlapping turns and interrupted refreshes are unmeasured
        # | in a live conversation; settle: T-082 with concurrent-turn replay.
        """
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            self._worker = threading.Thread(
                target=self._fetch,
                args=(query or self.query,),
                daemon=True,
                name="ebrain-pack-refresh",
            )
            self._worker.start()

    def wait(self, timeout: float = 5.0) -> None:
        """Join the outstanding refresh; callers that need a fresh pack may wait."""
        with self._lock:
            worker = self._worker
        if worker is not None:
            worker.join(timeout)

    def _fetch(self, query: str) -> None:
        """EXPERIMENTAL: ask the service for a rendered bundle, best effort.

        # UNTESTED: whether a stale or partial pack helps a real voice turn is
        # | unproven; settle: T-082 with a real-session harm audit.
        """
        rendered = ""
        if self.token:
            try:
                with self._factory(
                    timeout=REQUEST_TIMEOUT,
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    response = client.post(
                        self.url + "/v1/ebrain/query",
                        headers={
                            "Authorization": "Bearer " + self.token,
                            "Content-Type": "application/json",
                        },
                        json={
                            "ts": int(time.time()),
                            "text": query,
                            "token_budget": self.token_budget,
                        },
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if isinstance(payload, dict) and isinstance(
                        payload.get("rendered"), str
                    ):
                        rendered = payload["rendered"]
            except Exception:  # noqa: BLE001 - the bridge is deliberately best effort
                rendered = ""
        with self._lock:
            self._pack = rendered


class EBrainV3PackClient:
    """Additive schema-3 voice pack. Local opt-in; never speaks a guessed current.

    A pack is produced only from a validated V3 ``Answer`` supplied by the shared
    V3 service. Missing/unconfigured memory yields an empty, nonblocking pack.
    """

    def __init__(self, service: Any = None, *, max_chars: int = 1200) -> None:
        self.service = service
        self.max_chars = max_chars
        self._pack = ""

    @staticmethod
    def render(answer: Any, *, max_chars: int = 1200) -> str:
        from .v3.contracts import AnswerStatus, FactState

        lines = [
            f"[E-Brain V3 answer={answer.answer_status.value} "
            f"snapshot={answer.snapshot.knowledge_seq}]"
        ]
        for item in answer.items:
            if item.state is FactState.CURRENT:
                lines.append(
                    f"current: {item.key.predicate} = {item.current_value} "
                    f"[freshness={item.freshness}]"
                )
            elif item.state is FactState.CONFLICT:
                lines.append(f"conflict: {item.key.predicate} (no current; needs review)")
            elif item.state is FactState.PENDING_VERIFICATION:
                lines.append(f"pending: {item.key.predicate} (not current)")
            elif item.state is FactState.WITHDRAWN:
                lines.append(f"withdrawn: {item.key.predicate} (no current)")
            else:
                lines.append(f"unknown: {item.key.predicate} (no current)")
            for provenance in item.provenance[:1]:
                lines.append(f"  evidence={provenance.source_id}:{provenance.digest[:12]}")
        for flag in answer.degradation:
            lines.append(f"degraded: {flag}")
        if answer.answer_status is AnswerStatus.UNAVAILABLE:
            lines.append("memory unavailable; do not assume any remembered state")
        text = "\n".join(lines)
        if len(text) <= max_chars:
            return text
        # Keep the header, critical states and degradation; drop optional detail.
        kept = [lines[0]]
        for line in lines[1:]:
            if any(word in line for word in ("conflict", "pending", "withdrawn", "degraded", "unavailable")):
                kept.append(line)
        return "\n".join(kept)[:max_chars]

    def refresh(self, ctx: Any, selector: Any) -> str:
        """Best effort; an unconfigured service leaves the pack empty."""
        if self.service is None:
            self._pack = ""
            return self._pack
        try:
            answer = self.service.query(ctx, selector)
            self._pack = self.render(answer, max_chars=self.max_chars)
        except Exception:  # noqa: BLE001 - voice must never block on memory
            self._pack = ""
        return self._pack

    @property
    def pack(self) -> str:
        return self._pack
