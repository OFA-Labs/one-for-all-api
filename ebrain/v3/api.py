"""Versioned V3 HTTP surface under /v1/ebrain (disabled unless configured).

Thin service calls only: no duplicate authority implementation. Schema is
negotiated explicitly via ``X-EBrain-Schema``; V3 is never inferred from a field.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse

from .auth.context import build_context
from .clients.negotiation import check_answer_compatibility, negotiate
from .config import V3Config
from .contracts import (
    AuthorizedContext,
    Decision,
    SchemaVersion,
    Selector,
    Vote,
    WriteRequest,
)
from .errors import V3Error
from .service import V3Service


@dataclass
class V3ApiConfig:
    cfg: V3Config
    service: V3Service
    authenticate: Callable[[str], object]


def create_app(config: V3ApiConfig) -> FastAPI:
    app = FastAPI(title="E-Brain V3", version="3.0.0", docs_url=None, redoc_url=None)

    def context(
        scope: str,
        token: str | None,
        schema: str | None,
        request_id: str,
    ) -> AuthorizedContext:
        if not config.cfg.schema3_http_enabled:
            raise V3Error("schema-3 routes are disabled", code="unsupported_schema",
                          request_id=request_id)
        if negotiate(schema) is not SchemaVersion.V3:
            raise V3Error("this route requires schema 3", code="unsupported_schema",
                          request_id=request_id)
        if not token:
            raise V3Error("missing credential", code="unauthenticated", request_id=request_id)
        principal = config.authenticate(token)
        return build_context(principal, request_id=request_id, scope=scope)

    @app.exception_handler(V3Error)
    async def _error_handler(_: object, exc: V3Error) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.body().to_dict())

    @app.get("/v1/ebrain/health")
    def health() -> dict[str, object]:
        return {
            "schema": 3,
            "enabled": config.cfg.schema3_http_enabled,
            "disabled_flags": list(config.cfg.disabled_summary),
        }

    @app.post("/v1/ebrain/write")
    def write(
        request: WriteRequest,
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        return config.service.write(ctx, request).model_dump(mode="json")

    @app.post("/v1/ebrain/query")
    def query(
        request: Selector,
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        answer = config.service.query(ctx, request)
        compatibility = check_answer_compatibility(SchemaVersion.V3, answer)
        if not compatibility.compatible:
            raise V3Error(compatibility.reason, code="semantic_reject", request_id=x_request_id)
        return answer.model_dump(mode="json")

    @app.get("/v1/ebrain/limits")
    def limits(
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        return config.service.limits(ctx).model_dump(mode="json")

    @app.post("/v1/ebrain/proposals")
    def propose(
        request: dict,
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        return config.service.propose(ctx, Decision.model_validate(request)).model_dump(mode="json")

    @app.post("/v1/ebrain/proposals/{decision_id}/vote")
    def vote(
        decision_id: str,
        request: dict,
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        payload = dict(request)
        payload.setdefault("decision_id", decision_id)
        return config.service.vote(ctx, Vote.model_validate(payload)).model_dump(mode="json")

    @app.post("/v1/ebrain/proposals/{decision_id}/apply")
    def apply(
        decision_id: str,
        x_schema: str | None = Header(None, alias="X-EBrain-Schema"),
        x_scope: str = Header("", alias="X-EBrain-Scope"),
        x_token: str | None = Header(None, alias="X-EBrain-Token"),
        x_request_id: str = Header("unknown", alias="X-Request-ID"),
    ) -> dict[str, object]:
        ctx = context(x_scope, x_token, x_schema, x_request_id)
        return config.service.apply(ctx, decision_id).model_dump(mode="json")

    return app
