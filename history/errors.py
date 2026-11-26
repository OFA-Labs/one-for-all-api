"""One error envelope for History routes: ``{"error": {"code", "message"}}``.

FastAPI answers bad parameters with ``422 {"detail": [...]}`` and ``HTTPException`` with
``{"detail": "..."}``. History routes must use its own envelope while E-Brain keeps its current
shapes, so the handlers below only take over requests under the History path prefixes.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import (http_exception_handler,
                                        request_validation_exception_handler)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

HISTORY_PREFIXES = ("/v1/tasks", "/v1/history")
NO_STORE = {"Cache-Control": "private, no-store", "Vary": "Authorization"}

_STATUS_CODES = {401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "not_found",
                 409: "conflict", 413: "invalid_param", 503: "service_unavailable"}


class HistoryError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def envelope(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status,
                        headers=NO_STORE)


def _is_history(request: Request) -> bool:
    path = request.url.path
    return any(path == p or path.startswith(p + "/") for p in HISTORY_PREFIXES)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HistoryError)
    async def _history_error(_: Request, exc: HistoryError):
        return envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        if not _is_history(request):
            return await request_validation_exception_handler(request, exc)
        # Never echo the rejected input: it may contain goal text.
        return envelope(400, "invalid_param", "Invalid request parameter.")

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if not _is_history(request):
            return await http_exception_handler(request, exc)
        code = _STATUS_CODES.get(exc.status_code, "invalid_param" if exc.status_code < 500
                                 else "service_unavailable")
        return envelope(exc.status_code, code, "Request failed.")
