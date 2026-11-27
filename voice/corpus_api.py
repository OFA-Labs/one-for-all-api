"""Info Corpus routes (E-Brain page): "Use without consent" documents and private vault items.

Same protection as the other desktop routes (paired page only). Private values go in once and are never
returned; unlocking asks Windows to confirm it is you.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Document(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=64)
    text: str = Field(default="", max_length=200_000)


class PrivateItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    label: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{0,63}$")
    value: str = Field(min_length=1, max_length=4096)
    site: str = Field(pattern=r"^https://(\*\.)?[a-z0-9.-]{3,200}(:\d{1,5})?$|^app:.{3,200}$")
    sensitive: bool = False           # D2 (ID, bank, health) rather than D3 (password)

    def __repr__(self) -> str:        # never render the value
        return f"PrivateItem({self.service}/{self.label})"
    __str__ = __repr__


class Handle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    handle: str = Field(max_length=200)


def corpus_router(auth, core_of) -> APIRouter:
    router = APIRouter(prefix="/v1/corpus")

    def core(request: Request):
        auth(request)
        return core_of()

    def off():
        return JSONResponse({"code": "OFA_BRAIN_OFF"}, status_code=404)

    def bad(code: str, status: int = 400):
        return JSONResponse({"code": code}, status_code=status)

    @router.get("/open")
    async def documents(request: Request):
        try:
            return {"documents": core(request).deps.corpus.list()}
        except LookupError:
            return off()

    @router.get("/open/{name}")
    async def document(name: str, request: Request):
        try:
            return {"name": name, "text": core(request).deps.corpus.read(name)}
        except LookupError:
            return off()
        except (OSError, ValueError):
            return bad("NO_DOCUMENT", 404)

    @router.post("/open/save")
    async def save(request: Request):
        try:
            c = core(request)
            doc = Document.model_validate(await request.json())
            return c.deps.corpus.write(doc.name, doc.text)
        except LookupError:
            return off()
        except (ValidationError, ValueError):
            return bad("INVALID_DOCUMENT")

    @router.post("/open/delete")
    async def remove(request: Request):
        try:
            c = core(request)
            return {"deleted": c.deps.corpus.delete(Document.model_validate(await request.json()).name)}
        except LookupError:
            return off()
        except (ValidationError, ValueError):
            return bad("INVALID_DOCUMENT")

    def private_view(c) -> dict:
        keys = ("handle", "class", "service", "label", "allowed_targets", "revoked")
        return {"unlocked": c.vault.unlocked,
                "items": [{k: m[k] for k in keys if k in m} for m in c.vault.list(include_revoked=True)]}

    @router.get("/private")
    async def private(request: Request):
        try:
            return private_view(core(request))
        except LookupError:
            return off()

    @router.post("/private/{action}")
    async def change(action: str, request: Request):
        from ofa.vault.handles import HandleError
        from ofa.vault.store import VaultError, VaultLocked
        try:
            c = core(request)
            body = await request.json()
            if action == "unlock":
                await asyncio.to_thread(c.vault.unlock)
            elif action == "lock":
                c.vault.lock()
            elif action == "add":
                item = PrivateItem.model_validate(body)
                handle = c.vault.put("D2" if item.sensitive else "D3", item.service, item.label, item.value,
                                     allowed_targets=[item.site])
                c.audit.write("vault_put", handle_ids=[handle], result="ok")
            elif action in {"revoke", "delete"}:
                handle = Handle.model_validate(body).handle
                (c.vault.revoke if action == "revoke" else c.vault.delete)(handle)
                c.audit.write("vault_" + action, handle_ids=[handle], result="ok")
            else:
                return bad("UNKNOWN_ACTION", 404)
            return private_view(c)
        except LookupError:
            return off()
        except VaultLocked:
            return bad("VAULT_LOCKED", 423)
        except (ValidationError, VaultError, HandleError, ValueError):
            return bad("INVALID_ITEM")

    return router
