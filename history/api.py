"""History HTTP routes (``/v1/tasks``, ``/v1/history/*``). Mounted by ``oneforall.api``.

Member routes are read-only and owner-scoped (the user id comes from the token). ``POST
/v1/tasks`` is service-only: it is the seam for the future task engine and is never called by
the browser. Errors use the History envelope (see errors.py).
"""
from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Iterator

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from .auth import Principal, make_guards
from .config import MAX_BODY_BYTES
from .errors import NO_STORE, HistoryError, install_error_handlers
from .models import TASK_ID_RE, TaskIn
from .store import (CALENDAR_MAX_DAYS, MAX_LIST_LIMIT, MAX_QUERY_CHARS, PERIOD_MAX_DAYS, Filters,
                    HistoryStore, build_filters)

__all__ = ["create_router", "install_error_handlers"]
log = logging.getLogger("history")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _filters_dependency(*, require_range: bool, max_days: int | None):
    def dependency(
        q: str | None = Query(None, max_length=MAX_QUERY_CHARS),
        status: str | None = Query(None, max_length=32),
        state: str | None = Query(None, max_length=32),
        tier: str | None = Query(None, max_length=16),
        from_: str | None = Query(None, alias="from", max_length=10),
        to: str | None = Query(None, max_length=10),
        tz: str | None = Query(None, max_length=64),
        include_sample: str | None = Query(None, max_length=1),
        sort: str | None = Query(None, max_length=16),
    ) -> Filters:
        return build_filters(q=q, status=status, state=state, tier=tier, from_=from_, to=to,
                             tz=tz, include_sample=include_sample, sort=sort,
                             require_range=require_range, max_days=max_days)
    return dependency


def create_router(cfg: dict) -> APIRouter:
    tokens: dict = cfg.get("tokens") or {}
    if not cfg.get("cursor_secret"):
        log.warning("HISTORY_CURSOR_SECRET is not set; using an ephemeral cursor secret "
                    "(cursors stop working on restart). Set it outside development.")
        cfg = {**cfg, "cursor_secret": secrets.token_bytes(32)}
    max_body = int(cfg.get("max_body_bytes") or MAX_BODY_BYTES)
    member, service = make_guards(tokens)

    def no_store(response: Response) -> None:
        response.headers.update(NO_STORE)

    router = APIRouter(dependencies=[Depends(no_store)])

    def member_store(p: Principal = Depends(member)) -> Iterator[HistoryStore]:
        store = HistoryStore(cfg["data_dir"], cfg, p.user_id or "")
        try:
            yield store
        finally:
            store.close()

    list_filters = _filters_dependency(require_range=False, max_days=None)
    period_filters = _filters_dependency(require_range=True, max_days=PERIOD_MAX_DAYS)
    calendar_filters = _filters_dependency(require_range=True, max_days=CALENDAR_MAX_DAYS)

    # NOTE: the store dependency is declared first so authentication fails (401/403) before
    # any query-parameter validation can answer an unauthenticated caller.
    @router.get("/v1/tasks")
    def list_tasks(s: HistoryStore = Depends(member_store), f: Filters = Depends(list_filters),
                   cursor: str | None = Query(None, max_length=512),
                   limit: int = Query(20, ge=1, le=MAX_LIST_LIMIT)):
        return s.list_tasks(f, cursor=cursor, limit=limit)

    @router.get("/v1/history/period")
    def period(s: HistoryStore = Depends(member_store),
               f: Filters = Depends(period_filters)):
        return s.period(f)

    @router.get("/v1/history/calendar")
    def calendar(s: HistoryStore = Depends(member_store),
                 f: Filters = Depends(calendar_filters)):
        return s.calendar(f)

    def _detail(s: HistoryStore, task_id: str) -> dict:
        found = s.get_task(task_id) if TASK_ID_RE.match(task_id) else None
        if found is None:
            raise HistoryError(404, "not_found", "Task not found.")
        return found

    @router.get("/v1/tasks/{task_id}")
    def get_task(task_id: str, s: HistoryStore = Depends(member_store)):
        return _detail(s, task_id)

    @router.get("/v1/tasks/{task_id}/export")
    def export_task(task_id: str, s: HistoryStore = Depends(member_store)):
        _detail(s, task_id)
        body = s.export(task_id, now=_now_ms())
        return Response(json.dumps(body, indent=2), media_type="application/json",
                        headers={**NO_STORE,
                                 "Content-Disposition": f'attachment; filename="{task_id}.json"'})

    @router.post("/v1/tasks")
    async def ingest(request: Request, _: Principal = Depends(service)):
        declared = request.headers.get("content-length", "")
        if declared.isdigit() and int(declared) > max_body:
            raise HistoryError(413, "invalid_param", "Request body is too large.")
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > max_body:
                raise HistoryError(413, "invalid_param", "Request body is too large.")
            chunks.append(chunk)
        try:
            snapshot = TaskIn.model_validate_json(b"".join(chunks))
        except ValidationError:  # never echo the input: it may contain goal text
            raise HistoryError(400, "invalid_param", "Invalid task snapshot.") from None

        def work():
            store = HistoryStore(cfg["data_dir"], cfg, snapshot.user_id)
            try:
                return store.ingest(snapshot, now=_now_ms())
            finally:
                store.close()

        result = await run_in_threadpool(work)
        return JSONResponse(result.body, status_code=result.status, headers=NO_STORE)

    return router
