"""Separate loopback-only local API; no changes to existing OFA module APIs."""
from __future__ import annotations

import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .contracts import Answer, Command, Control, Decision, ExecutionError, Submission


def create_app(engine, token: str):
    if len(token) < 32:
        raise ValueError("Local API token must contain at least 32 characters")

    @asynccontextmanager
    async def lifespan(app):
        yield
        engine.close()
        for hand in engine.hands.values():
            if hasattr(hand, "close"):
                hand.close()

    app = FastAPI(title="OFA local execution", docs_url=None, redoc_url=None,
                  openapi_url=None, lifespan=lifespan)

    @app.middleware("http")
    async def local_security(request: Request, call_next):
        host = urlsplit("http://" + request.headers.get("host", "")).hostname
        if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            return JSONResponse({"code": "HOST_DENIED"}, status_code=403)
        origin = request.headers.get("origin")
        if origin and origin != f"{request.url.scheme}://{request.headers['host']}":
            return JSONResponse({"code": "ORIGIN_DENIED"}, status_code=403)
        if request.url.path.startswith("/api/"):
            supplied = request.headers.get("authorization", "")
            if not hmac.compare_digest(supplied, "Bearer " + token):
                return JSONResponse({"code": "UNAUTHENTICATED"}, status_code=401)
            if int(request.headers.get("content-length", "0")) > 131072:
                return JSONResponse({"code": "REQUEST_TOO_LARGE"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'"
        return response

    @app.exception_handler(ExecutionError)
    async def execution_error(request, exc):
        return JSONResponse({"code": exc.code, "message": exc.message, "options": exc.options}, status_code=409)

    @app.get("/")
    def page():
        return FileResponse(Path(__file__).with_name("ui") / "index.html")

    @app.get("/control.js")
    def script():
        return FileResponse(Path(__file__).with_name("ui") / "control.js", media_type="text/javascript")

    @app.get("/control.css")
    def css():
        return FileResponse(Path(__file__).with_name("ui") / "control.css", media_type="text/css")

    @app.get("/api/capabilities")
    def capabilities():
        return engine.capabilities()

    @app.get("/api/tasks")
    def tasks():
        return [engine.snapshot(t) for t in list(engine.tasks)]

    @app.post("/api/tasks")
    def submit(body: Submission):
        return engine.submit(body.command_id, body.plan)

    @app.post("/api/commands")
    def command(body: Command):
        return engine.command(body)

    @app.get("/api/tasks/{task_id}")
    def task(task_id: str):
        return engine.snapshot(task_id)

    @app.post("/api/tasks/{task_id}/decision")
    def decision(task_id: str, body: Decision):
        return engine.decide(task_id, body)

    @app.post("/api/tasks/{task_id}/answer")
    def answer(task_id: str, body: Answer):
        return engine.answer(task_id, body)

    @app.post("/api/tasks/{task_id}/control")
    def control(task_id: str, body: Control):
        return engine.control(task_id, body)

    @app.post("/api/control")
    def global_control(body: Control):
        return engine.control(None, body)

    return app
