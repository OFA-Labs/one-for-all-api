"""Schema-3 MCP tool server (transport-agnostic dispatcher).

No SQL, shell, arbitrary file access or URL fetch is exposed. Every tool call
delegates to the shared V3Service; authorization comes from the server-derived
context, never from tool arguments.
"""
from __future__ import annotations

from typing import Any

from .clients.negotiation import negotiate
from .config import V3Config
from .contracts import Selector, WriteRequest
from .errors import Malformed, UnsupportedSchema
from .service import V3Service

TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "ebrain.query": {
        "type": "object",
        "properties": {"schema": {"type": "string"}, "scope": {"type": "string"},
                       "text": {"type": "string"}, "predicate": {"type": "string"}},
        "required": ["scope"],
    },
    "ebrain.write": {
        "type": "object",
        "properties": {"schema": {"type": "string"}, "op_id": {"type": "string"},
                       "value": {}, "idempotency_key": {"type": "string"}},
        "required": ["op_id", "idempotency_key"],
    },
    "ebrain.limits": {"type": "object", "properties": {"scope": {"type": "string"}}},
}


class McpServer:
    def __init__(self, service: V3Service, cfg: V3Config | None = None) -> None:
        self.service = service
        self.cfg = (cfg or V3Config()).validate()

    def tools(self) -> dict[str, dict[str, Any]]:
        if not self.cfg.mcp_enabled:
            return {}
        return dict(TOOL_SCHEMAS)

    def dispatch(self, ctx: Any, name: str, arguments: dict[str, Any]) -> Any:
        if not self.cfg.mcp_enabled:
            raise UnsupportedSchema("MCP tools are disabled")
        if name not in TOOL_SCHEMAS:
            raise Malformed("unknown MCP tool")
        negotiate(arguments.get("schema", "3"))
        if any(token in str(arguments).lower() for token in
               ("sql", "shell", "powershell", "http://", "https://", "file://")):
            raise Malformed("MCP tools cannot access SQL, shell, files or URLs")
        if name == "ebrain.query":
            return self.service.query(ctx, Selector.model_validate(arguments))
        if name == "ebrain.write":
            return self.service.write(ctx, WriteRequest.model_validate(arguments))
        return self.service.limits(ctx).model_dump(mode="json")
