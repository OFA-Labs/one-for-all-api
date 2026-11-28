"""Loopback server for the vault enrollment page and its dry-run mock forms (§8.5).
Bound to 127.0.0.1 only, per-process bearer token, same-origin only, vault bodies never logged."""
from __future__ import annotations

import asyncio
import hmac
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from .vault.handles import HandleError
from .vault.store import VaultError, VaultLocked

UI = Path(__file__).with_name("ui")
class Secret(BaseModel):
    data_class: str = Field(pattern=r"^D[0-3]$")
    service: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    label: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    value: str = Field(min_length=1, max_length=4096)
    allowed_targets: list[str] = Field(default_factory=list, max_length=20)
    description: str = Field(default="", max_length=200)
    expected_account: str = Field(default="", max_length=200)

    def __repr__(self) -> str:          # never render the value
        return f"Secret({self.data_class}/{self.service}/{self.label})"
    __str__ = __repr__


class Targets(BaseModel):
    allowed_targets: list[str] = Field(max_length=20)


class Pref(BaseModel):
    key: str = Field(pattern=r"^(preferred_name|script|reply_language|never_send_d1|sessions)$")
    value: object


def create_app(core, token: str | None = None) -> FastAPI:
    token = token or secrets.token_urlsafe(32)
    app = FastAPI(title="OFA local", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.token = token
    def auth(authorization: str = Header(default="")) -> None:
        given = authorization.removeprefix("Bearer ").strip()
        if not given or not hmac.compare_digest(given, token):
            raise HTTPException(401, "unauthorized")

    @app.middleware("http")
    async def loopback_only(request: Request, call_next):
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "loopback only"}, 403)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"ok": True, "service": "ofa"}

    # --- vault --------------------------------------------------------------------------------
    @app.get("/vault", response_class=HTMLResponse)
    def vault_page():
        return (UI / "vault.html").read_text(encoding="utf-8")

    @app.post("/vault/api/unlock", dependencies=[Depends(auth)])
    async def unlock():
        ok = await asyncio.to_thread(core.vault.unlock)
        return {"unlocked": ok}

    @app.post("/vault/api/lock", dependencies=[Depends(auth)])
    def lock():
        core.vault.lock()
        return {"unlocked": False}

    @app.get("/vault/api/items", dependencies=[Depends(auth)])
    def items():
        return {"unlocked": core.vault.unlocked, "items": core.vault.list(include_revoked=True),
                "managers": {k: v.status() for k, v in core.broker.managers.items()},
                "profile": core.memory.profile()}

    @app.post("/vault/api/items", dependencies=[Depends(auth)])
    def put(item: Secret):
        try:
            h = core.vault.put(item.data_class, item.service, item.label, item.value,
                               allowed_targets=item.allowed_targets, description=item.description,
                               expected_account=item.expected_account)
        except VaultLocked:
            raise HTTPException(423, "vault locked")
        except (VaultError, HandleError) as exc:
            raise HTTPException(400, str(exc))
        core.audit.write("vault_put", handle_ids=[h], result="ok")
        return {"handle": h}

    @app.post("/vault/api/items/{handle:path}/targets", dependencies=[Depends(auth)])
    def targets(handle: str, t: Targets):
        core.vault.set_targets(handle, t.allowed_targets)
        core.audit.write("vault_targets", handle_ids=[handle], result="ok")
        return {"ok": True}

    @app.post("/vault/api/items/{handle:path}/revoke", dependencies=[Depends(auth)])
    def revoke(handle: str):
        core.vault.revoke(handle)
        core.audit.write("vault_revoke", handle_ids=[handle], result="ok")
        return {"ok": True}

    @app.delete("/vault/api/items/{handle:path}", dependencies=[Depends(auth)])
    def delete(handle: str):
        core.vault.delete(handle)
        core.audit.write("vault_delete", handle_ids=[handle], result="ok")
        return {"ok": True}

    @app.post("/vault/api/pref", dependencies=[Depends(auth)])
    def pref(p: Pref):
        core.memory.set(p.key, p.value)
        return {"ok": True}

    @app.post("/vault/api/dry-run", dependencies=[Depends(auth)])
    async def dry_run():
        """Fill mock login with the user's mock handle to show the broker working, origin-verified."""
        from .vault.broker import TargetIdentity

        class Box:
            value = ""

            def set_value(self, ref, v):
                Box.value = "•" * len(v)
                return True

            def field_length(self, ref):
                return len(Box.value)
        hs = core.vault.find(service="ofa-mock")
        if not hs:
            raise HTTPException(404, "Save a test secret for service 'ofa-mock' first")
        good = core.broker.fill(hs[0]["handle"], "pw", TargetIdentity("browser", "http://127.0.0.1:8768/mock/login",
                                                                       True, field_is_password=True), Box())
        bad = core.broker.fill(hs[0]["handle"], "pw", TargetIdentity("browser", "http://localhost:8768/mock/login",
                                                                      True, field_is_password=True), Box())
        return {"verified_origin": {"ok": good.ok, "reason": good.reason}, "lookalike": {"ok": bad.ok, "reason": bad.reason}}

    # --- mock pages for dry-run fills (§8.5) --------------------------------------------------------
    @app.get("/mock/{page}", response_class=HTMLResponse)
    def mock(page: str):
        f = UI / f"mock-{page}.html"
        if not f.exists():
            raise HTTPException(404)
        return f.read_text(encoding="utf-8")

    return app


async def serve(app: FastAPI, port: int) -> None:
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
    server = uvicorn.Server(config)
    await server.serve()
