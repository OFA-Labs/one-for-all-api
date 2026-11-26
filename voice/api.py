"""Observer/control socket; native physical activation owns microphone arming."""
from __future__ import annotations

import asyncio
import hmac
import json
from contextlib import suppress
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, WebSocket, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketDisconnect

from .config import Settings
from .events import Events
from .pairing import GrantRevoked


def create_app(settings: Settings, events: Events, session: Any, token: str,
               pairing=None, catalog=None, runtime=None, shutdown=None) -> FastAPI:
    if len(token) < 32:
        raise ValueError("Local observer token must be at least 32 characters")
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.origins),
                       allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Authorization", "Content-Type"], max_age=300)

    def finish(response, origin):
        # Errors caught by this outer security middleware do not traverse the
        # inner CORS middleware. Give only the configured caller readable errors.
        if origin in settings.origins:
            response.headers["Access-Control-Allow-Origin"]=origin
            if "origin" not in response.headers.get("Vary","").lower().split(","):
                response.headers.add_vary_header("Origin")
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        return response

    @app.middleware("http")
    async def security(request: Request, call_next):
        host = urlsplit("http://" + request.headers.get("host", "")).hostname
        origin = request.headers.get("origin")
        if host not in {"127.0.0.1", "localhost"}:
            return finish(JSONResponse({"code": "HOST_DENIED"}, status_code=403),origin)
        if origin and origin not in settings.origins:
            return finish(JSONResponse({"code": "ORIGIN_DENIED"}, status_code=403),origin)
        if request.method == "POST":
            if origin not in settings.origins:
                return finish(JSONResponse({"code": "ORIGIN_REQUIRED"}, status_code=403),origin)
            if request.headers.get("content-type", "").split(";")[0] != "application/json":
                return finish(JSONResponse({"code": "JSON_REQUIRED"}, status_code=415),origin)
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 8192:
                    return finish(JSONResponse({"code": "REQUEST_TOO_LARGE"}, status_code=413),origin)
            request._body = bytes(body)
        try:
            response = await call_next(request)
        except GrantRevoked:
            response = JSONResponse({"code": "GRANT_REVOKED"}, status_code=410)
        except (KeyError, TypeError):
            response = JSONResponse({"code": "INVALID_REQUEST"}, status_code=400)
        except (PermissionError, ValueError):
            response = JSONResponse({"code": "CONNECTION_DENIED"}, status_code=403)
        except Exception as exc:
            from ofa_execution.contracts import ExecutionError
            if not isinstance(exc,ExecutionError): raise
            response = JSONResponse({"code":exc.code,"message":exc.message},status_code=409)
        return finish(response,origin)

    def auth(request):
        if pairing is None:
            raise PermissionError("Pairing unavailable")
        origin = request.headers.get("origin", "")
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        pairing.authorize(origin, token)
        return origin, token

    @app.get("/v1/health")
    async def health():
        # Only configuration *state* is exposed here. Keys stay SecretStr and
        # are never serialized into an HTTP response or an observer event.
        speech = {
            "mode": settings.mode,
            "language": settings.language,
            "headphones": settings.headphones,
            "command_only": settings.command_only,
            "stt_order": list(settings.stt_order),
            "tts_order": list(settings.tts_order),
            "deepgram_configured": bool(settings.deepgram_key.get_secret_value()),
            "gradium_configured": bool(settings.gradium_key.get_secret_value()),
            "engine_enabled": False,
        }
        return {"service": "ofa-desktop", "version": "0.2.3", "os": "windows",
                "identity_mode": "local-development", "llm_enabled": False,
                "speech": speech}

    @app.post("/v1/pairing")
    async def begin(request: Request):
        if pairing is None:
            raise PermissionError("Pairing unavailable")
        body = await request.json()
        return pairing.begin(request.headers["origin"], body["public_key"])

    @app.get("/v1/pairing/{request_id}")
    async def poll(request_id: str, request: Request):
        if pairing is None:
            raise PermissionError("Pairing unavailable")
        return pairing.poll(request.headers.get("origin", ""), request_id)

    @app.post("/v1/challenge")
    async def challenge(request: Request):
        if pairing is None:
            raise PermissionError("Pairing unavailable")
        body = await request.json()
        try:
            return pairing.challenge(request.headers["origin"], body["grant_id"])
        except GrantRevoked:
            return JSONResponse({"code": "GRANT_REVOKED"}, status_code=410)

    @app.post("/v1/session")
    async def authenticate(request: Request):
        if pairing is None:
            raise PermissionError("Pairing unavailable")
        body = await request.json()
        return pairing.authenticate(request.headers["origin"], body["grant_id"],
                                    body["challenge_id"], body["signature"])

    @app.post("/v1/heartbeat")
    async def heartbeat(request: Request):
        origin, credential = auth(request)
        pairing.heartbeat(origin, credential)
        return {"connected": True, "state": events.latest.get("state", "IDLE")}

    @app.post("/v1/ticket")
    async def ticket(request: Request):
        origin, credential = auth(request)
        return {"ticket": pairing.ticket(origin, credential)}

    @app.get("/v1/apps")
    async def apps(request: Request):
        auth(request)
        return catalog() if catalog else []

    @app.post("/v1/disconnect")
    async def disconnect(request: Request):
        origin, credential = auth(request)
        # The UI disconnects this computer, including other tabs/browser grants.
        # This is also the current sign-out hook until real identity is supplied.
        pairing.invalidate_all()
        if runtime: runtime.revoke()
        await session.close()
        return {"connected": False}

    @app.get("/v1/desktop/status")
    async def desktop_status(request: Request):
        auth(request)
        return runtime.status() if runtime else {}

    @app.post("/v1/desktop/scopes")
    async def scope(request: Request):
        origin,_=auth(request)
        if not runtime: raise ValueError()
        return runtime.request_scope((await request.json())["kind"],origin)

    @app.get("/v1/desktop/scopes/{request_id}")
    async def poll_scope(request_id: str,request: Request):
        origin,_=auth(request)
        if not runtime: raise ValueError()
        return runtime.poll_scope(request_id,origin)

    @app.post("/v1/apps/refresh")
    async def refresh_apps(request: Request):
        auth(request)
        if not runtime or not runtime.refresh_catalog or runtime.bridge._active: raise ValueError()
        runtime.refresh_catalog(True)
        return catalog()

    @app.post("/v1/apps/choose")
    async def choose_app(request: Request):
        auth(request)
        if not runtime: raise ValueError()
        body=await request.json()
        # Return immediately: native verification/progress remains on the
        # authenticated event stream. Consume the offered ID synchronously.
        option=body["option_id"]
        if option not in runtime.choices: raise ValueError()
        asyncio.create_task(runtime.choose_app(option))
        return {"queued":True}

    @app.post("/v1/desktop/decision")
    async def decision(request: Request):
        auth(request)
        body=await request.json()
        if not runtime: raise ValueError()
        return runtime.bridge.decide(body["task_id"],body["decision"])

    @app.post("/v1/desktop/answer")
    async def answer(request: Request):
        auth(request)
        body=await request.json()
        if not runtime: raise ValueError()
        return runtime.bridge.answer(body["task_id"],body["answer"])

    @app.post("/v1/desktop/continue")
    async def continue_task(request: Request):
        auth(request)
        body=await request.json()
        if not runtime: raise ValueError()
        return runtime.bridge.continue_task(body["task_id"],body["handoff_id"])

    @app.post("/v1/desktop/quit")
    async def quit_host(request: Request):
        auth(request)
        await session.close("quit")
        if shutdown: shutdown()
        return {"stopping":True}

    @app.post("/v1/voice/stop")
    async def stop(request: Request):
        auth(request)
        await session.close()
        return {"stopped": True}

    @app.websocket("/v1/voice/events")
    async def socket(ws: WebSocket) -> None:
        host = urlsplit("http://" + ws.headers.get("host", "")).hostname
        origin = ws.headers.get("origin", "")
        if host not in {"127.0.0.1", "localhost"} or origin not in settings.origins:
            await ws.close(code=1008)
            return
        await ws.accept()
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(32)
        sender: asyncio.Task[None] | None = None
        credential = None
        try:
            auth = await asyncio.wait_for(ws.receive_text(), timeout=2)
            if len(auth) > 4096:
                await ws.close(code=1009)
                return
            body = json.loads(auth)
            if not isinstance(body, dict):
                await ws.close(code=1008)
                return
            if pairing is not None:
                if body.get("type") != "auth" or len(events.observers) >= 4:
                    raise PermissionError("Observer limit")
                credential = pairing.consume(origin, str(body.get("ticket", "")))
            elif body.get("type") != "auth" or not hmac.compare_digest(
                str(body.get("token", "")), token
            ) or events.observers:
                await ws.close(code=1008)
                return
            events.observers.add(queue)
            await ws.send_json(events.snapshot())

            async def send() -> None:
                while True:
                    if credential:
                        try:
                            pairing.authorize(origin, credential)
                        except PermissionError:
                            await ws.close(code=1008)
                            return
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=1)
                    except TimeoutError:
                        continue
                    if event["type"] == "disconnect":
                        await ws.close(code=1013)
                        return
                    await ws.send_json(event)

            sender = asyncio.create_task(send())
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if message.get("bytes") is not None:
                    await ws.close(code=1003)
                    return
                raw = message.get("text", "")
                if len(raw) > 4096:
                    await ws.close(code=1009)
                    return
                command = json.loads(raw)
                if credential:
                    pairing.authorize(origin, credential)
                if command == {"type": "stop"}:
                    await session.close()
                else:
                    await ws.close(code=1008)
                    return
        except (WebSocketDisconnect, TimeoutError, ValueError, PermissionError):
            with suppress(RuntimeError):
                await ws.close(code=1008)
            return
        finally:
            events.observers.discard(queue)
            if sender:
                sender.cancel()
                with suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await sender

    return app
