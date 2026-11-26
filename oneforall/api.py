"""Combined ONE FOR ALL API: the unchanged E-Brain app plus the History router.

Run: ``uvicorn oneforall.api:app --host 127.0.0.1 --port 8765``. It replaces ``ebrain.api:app`` as
the single local server, so ``EBRAIN_URL`` and the E-Brain CLI/hooks are unchanged.

E-Brain and History take **separate** configs: ``ebrain.api.create_app`` merges its argument into
its own defaults, so sharing one dict would leak keys between the two. The combined app also
inherits E-Brain's CORS middleware (127.0.0.1:3000/3100, bearer headers, no cookies); History
does not need it because the browser reaches History through the Next.js proxy.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ebrain.api import create_app as create_ebrain_app
from ebrain.api import load_config as load_ebrain_config
from ebrain.store import Store as EBrainStore
from history import schema
from history.api import create_router, install_error_handlers
from history.config import load_config as load_history_config


def create_app(ebrain_config: dict | None = None, history_config: dict | None = None) -> FastAPI:
    app = create_ebrain_app(ebrain_config)
    ecfg = load_ebrain_config() if ebrain_config is None else {**load_ebrain_config({}),
                                                                **ebrain_config}
    hcfg = load_history_config() if history_config is None else {**load_history_config({}),
                                                                 **history_config}
    app.include_router(create_router(hcfg))
    install_error_handlers(app)

    @app.get("/healthz")
    def healthz():
        # Public and detail-free: it reports only which subsystem is unavailable.
        status = {"ebrain": "ok", "history": "ok"}
        try:
            EBrainStore(ecfg["data_dir"], ecfg, "healthz").close()
        except Exception:  # noqa: BLE001 - any failure means "unavailable"
            status["ebrain"] = "unavailable"
        try:
            db = schema.connect(hcfg["data_dir"])
            try:
                status["history_schema"] = schema.schema_version(db)
            finally:
                db.close()
        except Exception:  # noqa: BLE001
            status["history"] = "unavailable"
        ok = status["ebrain"] == "ok" and status["history"] == "ok"
        return JSONResponse({"ok": ok, **status}, status_code=200 if ok else 503)

    return app


app = create_app()
