"""E-Brain HTTP API (FastAPI). Ships as ``one-for-all-api/ebrain/api.py``.

Run: ``uvicorn ebrain.api:app --host 127.0.0.1 --port 8765``.
Contract (FINAL/03-interfaces.md section 3):
  * 401 when the bearer token is missing or unknown. EBRAIN_TOKENS unset/invalid => EVERY request is
    401 (fail closed); the module still imports.
  * 422 (pydantic) when the JSON shape is wrong: missing field, wrong JSON type.
  * 200 + {"accepted": false, "reason": ...} when the shape is right but the store rejects the value.
  * agent_id and user_id come from the token, never from the body. supersedes list -> tuple.
  * One Store (one sqlite connection) per request; nothing is shared across the threadpool.
"""
from __future__ import annotations

import json
import os
from typing import Iterator

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from .models import Query, Trace, Write
from .store import DEFAULTS, Store, UnknownTarget

DEFAULT_PROJECT = "one-for-all"
FACTS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "limits_facts.json")
FAR_FUTURE = 2 ** 62
_INT_KEYS = {"capacity_soft", "capacity_hard", "rank_max_chains", "snippet_max_tokens",
             "max_text_chars", "default_token_budget", "api_port"}
_FLOAT_KEYS = {"join_auto_threshold", "join_review_threshold", "join_weight_tokens",
               "slot_match_threshold", "slot_match_threshold_external"}


def load_config(env: dict | None = None) -> dict:
    """Reads EBRAIN_<KEY> for every key in 08-config.md; invalid EBRAIN_TOKENS -> {} (fail closed)."""
    env = os.environ if env is None else env
    cfg: dict = {**DEFAULTS, "default_token_budget": 1024,
                 "data_dir": os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                                          "one-for-all", "ebrain")}
    for key in list(cfg):
        raw = env.get("EBRAIN_" + key.upper())
        if raw is not None:
            cfg[key] = int(raw) if key in _INT_KEYS else float(raw) if key in _FLOAT_KEYS else raw
    try:
        tokens = json.loads(env.get("EBRAIN_TOKENS", ""))
        cfg["tokens"] = tokens if isinstance(tokens, dict) else {}
    except ValueError:
        cfg["tokens"] = {}
    return cfg


class WriteIn(BaseModel):
    op_id: str
    ts: int
    project_id: str = DEFAULT_PROJECT
    visibility: str
    kind: str
    text: str
    path: str | None = None
    authority: str = "agent"
    provenance: str = "first_party"
    supersedes: list[str] = []
    deleted: bool = False


class QueryIn(BaseModel):
    query_id: str = "q"
    ts: int
    project_id: str = DEFAULT_PROJECT
    text: str
    token_budget: int | None = None
    as_of: int | None = None


class ObserveIn(BaseModel):
    session_id: str
    ts: int
    project_id: str = DEFAULT_PROJECT
    shown: list[str] = []
    followed: list[str] = []
    ignored: list[str] = []
    note: str = ""


class MaintainIn(BaseModel):
    now: int
    project_id: str | None = None


class PairIn(BaseModel):
    project_id: str = DEFAULT_PROJECT
    a: str
    b: str
    ts: int


class ApproveIn(BaseModel):
    ts: int


class ResolveIn(BaseModel):
    project_id: str = DEFAULT_PROJECT
    chain: str
    pick_op_id: str
    ts: int


class RollbackIn(BaseModel):
    to_ts: int
    project_id: str | None = None


def create_app(config: dict | None = None) -> FastAPI:
    cfg = load_config() if config is None else {**load_config({}), **config}
    tokens: dict = cfg.get("tokens") or {}
    with open(FACTS_PATH, encoding="utf-8") as f:
        facts = json.load(f)
    app = FastAPI(title="E-Brain", version="1.0.0")

    def principal(authorization: str | None = Header(default=None)) -> dict:
        tok = (authorization or "").removeprefix("Bearer ").strip()
        p = tokens.get(tok) if tok else None
        if not isinstance(p, dict) or not p.get("user") or not p.get("agent"):
            raise HTTPException(401, "missing or unknown bearer token")
        return {"user": p["user"], "agent": p["agent"], "human": bool(p.get("human"))}

    def human(p: dict = Depends(principal)) -> dict:
        if not p["human"]:
            raise HTTPException(403, "human token required")
        return p

    def open_store(p: dict = Depends(principal)) -> Iterator[Store]:
        s = Store(cfg["data_dir"], cfg, p["user"])  # one connection per request
        try:
            yield s
        finally:
            s.close()

    @app.post("/v1/ebrain/write")
    def write(body: WriteIn, p: dict = Depends(principal), s: Store = Depends(open_store)):
        authority = body.authority if (body.authority != "human" or p["human"]) else "agent"
        ack = s.write(Write(body.op_id, body.ts, p["agent"], body.project_id, body.visibility,
                            body.kind, body.text, body.path, authority, body.provenance,
                            tuple(body.supersedes), body.deleted))
        return {"accepted": ack.accepted, "reason": ack.reason}

    @app.post("/v1/ebrain/query")
    def query(body: QueryIn, p: dict = Depends(principal), s: Store = Depends(open_store)):
        b = s.query(Query(body.query_id, body.ts, p["agent"], body.project_id, body.text,
                          body.token_budget or cfg["default_token_budget"], body.as_of))
        return {"items": [{"item_id": i.item_id, "text": i.text, "status": i.status,
                           "source_op_ids": list(i.source_op_ids), "flags": list(i.flags),
                           "score": i.score} for i in b.items],
                "rendered": b.rendered,
                "capacity_state": s.limits(body.project_id)["capacity_state"]}

    @app.post("/v1/ebrain/observe")
    def observe(body: ObserveIn, p: dict = Depends(principal), s: Store = Depends(open_store)):
        s.observe(Trace(body.session_id, body.ts, p["agent"], body.project_id, tuple(body.shown),
                        tuple(body.followed), tuple(body.ignored), body.note))
        return {"ok": True}

    @app.post("/v1/ebrain/maintain")
    def maintain(body: MaintainIn, s: Store = Depends(open_store)):
        return {"actions": list(s.maintain(body.now, body.project_id).actions)}

    @app.get("/v1/ebrain/limits")
    def limits(project: str = DEFAULT_PROJECT, s: Store = Depends(open_store)):
        return {**facts, **s.limits(project)}  # dynamic numbers override static facts

    @app.get("/v1/ebrain/chains")
    def chains(project: str = DEFAULT_PROJECT, cursor: int = 0, limit: int = 50,
               ts: int = FAR_FUTURE, p: dict = Depends(principal), s: Store = Depends(open_store)):
        limit = max(1, min(limit, 200))
        rows = s.chains(project, p["agent"], ts, cursor, limit)
        return {"chains": rows, "next_cursor": str(cursor + limit) if len(rows) == limit else None}

    @app.get("/v1/ebrain/chains/{chain}")
    def chain(chain: str, project: str = DEFAULT_PROJECT, as_of: int = FAR_FUTURE,
              p: dict = Depends(principal), s: Store = Depends(open_store)):
        try:
            return {"chain": chain, "versions": s.chain_versions(project, chain, p["agent"], as_of)}
        except UnknownTarget:
            raise HTTPException(404, "unknown chain") from None

    @app.get("/v1/ebrain/pairs")
    def pairs(project: str = DEFAULT_PROJECT, p: dict = Depends(principal),
              s: Store = Depends(open_store)):
        return {"pairs": s.possible_pairs(project, p["agent"], FAR_FUTURE)}

    def _pair(kind: str, body: PairIn, s: Store) -> dict:
        try:
            (s.confirm_same if kind == "confirm" else s.split_same)(body.project_id, body.a, body.b,
                                                                     body.ts)
        except UnknownTarget:
            raise HTTPException(404, "unknown chain") from None
        return {"ok": True}

    @app.post("/v1/ebrain/pairs/confirm")
    def pair_confirm(body: PairIn, _: dict = Depends(human), s: Store = Depends(open_store)):
        return _pair("confirm", body, s)

    @app.post("/v1/ebrain/pairs/split")
    def pair_split(body: PairIn, _: dict = Depends(human), s: Store = Depends(open_store)):
        return _pair("split", body, s)

    @app.get("/v1/ebrain/heal")
    def heal(project: str = DEFAULT_PROJECT, s: Store = Depends(open_store)):
        return s.heal_state(project)

    @app.post("/v1/ebrain/heal/{op_id}/approve")
    def approve(op_id: str, body: ApproveIn, _: dict = Depends(human),
                s: Store = Depends(open_store)):
        try:
            s.approve_heal(op_id, body.ts)
        except UnknownTarget:
            raise HTTPException(404, "no proposal for this op") from None
        return {"ok": True}

    @app.post("/v1/ebrain/resolve")
    def resolve(body: ResolveIn, p: dict = Depends(human), s: Store = Depends(open_store)):
        try:
            versions = s.chain_versions(body.project_id, body.chain, p["agent"], body.ts)
        except UnknownTarget:
            raise HTTPException(404, "unknown chain") from None
        pick = next((v for v in versions if v["op_id"] == body.pick_op_id), None)
        if pick is None:
            raise HTTPException(404, "pick_op_id not in chain")
        live = tuple(v["op_id"] for v in versions if v["status"] in ("current", "conflicted"))
        op_id = f"human-{body.pick_op_id}-{body.ts}"
        ack = s.write(Write(op_id, body.ts, p["agent"], body.project_id, "shared", "decision",
                            pick["text"], None, "human", "first_party", live or (pick["op_id"],)))
        return {"accepted": ack.accepted, "reason": ack.reason, "op_id": op_id}

    @app.post("/v1/ebrain/rollback")
    def rollback(body: RollbackIn, _: dict = Depends(human), s: Store = Depends(open_store)):
        s.rollback(body.to_ts, body.project_id)
        return {"ok": True}

    @app.delete("/v1/ebrain/me")
    def delete_me(s: Store = Depends(open_store)):
        return {"deleted_rows": s.delete_user()}

    return app


app = create_app()
