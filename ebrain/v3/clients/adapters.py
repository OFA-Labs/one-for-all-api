"""CLI, MCP and voice adapters. All delegate to the same V3Service."""
from __future__ import annotations

from dataclasses import dataclass

from ..config import V3Config
from ..contracts import Answer, AnswerStatus, AuthorizedContext, Selector, WriteRequest, digest_of
from ..errors import Malformed, UnsupportedSchema
from ..projections.answers import Delivery, clip
from ..service import V3Service
from .negotiation import check_answer_compatibility, negotiate


@dataclass
class CliAdapter:
    service: V3Service

    def pack(self, ctx: AuthorizedContext, selector: Selector, schema: str | None = "3") -> Delivery:
        version = negotiate(schema)
        answer = self.service.query(ctx, selector)
        compatibility = check_answer_compatibility(version, answer)
        if not compatibility.compatible:
            return Delivery(
                answer.model_copy(update={
                    "answer_status": AnswerStatus.UNAVAILABLE,
                    "items": (),
                    "degradation": (*answer.degradation, "incompatible_client"),
                }),
                0, ("all",),
            )
        return clip(answer, ctx.principal.auth_epoch and 4096 or 4096)

    def remember(self, ctx: AuthorizedContext, request: WriteRequest) -> dict[str, object]:
        receipt = self.service.write(ctx, request)
        return {"op_id": receipt.op_id, "status": receipt.status.value,
                "knowledge_seq": receipt.knowledge_seq, "receipt_digest": receipt.request_digest}

    def maintain(self, ctx: AuthorizedContext, job_type: str) -> dict[str, object]:
        allowed = {"lint", "consolidate", "rebuild"}
        if job_type not in allowed:
            raise Malformed("maintenance job type is not allowed")
        return {"queued": True, "job_type": job_type,
                "scope": ctx.scope, "admin_grant_required": True}


@dataclass(frozen=True)
class McpToolDefinition:
    name: str
    description: str
    input_schema: dict[str, object]


MCP_TOOLS: tuple[McpToolDefinition, ...] = (
    McpToolDefinition("ebrain.query", "Query authorized memory", {"type": "object", "properties": {"schema": {"type": "string"}}}),
    McpToolDefinition("ebrain.evidence", "Read authorized evidence", {"type": "object"}),
    McpToolDefinition("ebrain.propose", "Propose a reviewed change", {"type": "object"}),
    McpToolDefinition("ebrain.write", "Append an authorized claim", {"type": "object"}),
)


@dataclass
class McpAdapter:
    service: V3Service
    cfg: V3Config

    def tools(self) -> tuple[McpToolDefinition, ...]:
        if not self.cfg.mcp_enabled:
            return ()
        return MCP_TOOLS

    def call_tool(self, ctx: AuthorizedContext, name: str, payload: dict[str, object]) -> object:
        if not self.cfg.mcp_enabled:
            raise UnsupportedSchema("MCP tools are disabled")
        if name not in {t.name for t in MCP_TOOLS}:
            raise Malformed("unknown MCP tool")
        if any(forbidden in str(payload).lower() for forbidden in ("sql", "shell", "http://", "https://", "file://")):
            raise Malformed("MCP tools cannot access SQL, shell, files or URLs")
        if name == "ebrain.query":
            return self.service.query(ctx, Selector.model_validate(payload.get("selector", {"scope": ctx.scope})))
        if name == "ebrain.write":
            return self.service.write(ctx, WriteRequest.model_validate(payload))
        return {"delegated": name, "scope": ctx.scope}


@dataclass
class VoicePack:
    scope: str
    query_digest: str
    snapshot_seq: int
    expiry: str
    answer: Answer | None = None


@dataclass
class VoiceAdapter:
    service: V3Service
    cfg: V3Config
    _pack: VoicePack | None = None

    def refresh(self, ctx: AuthorizedContext, selector: Selector) -> VoicePack:
        """Refresh is off the critical path; stale packs are never current."""
        answer = self.service.query(ctx, selector)
        pack = VoicePack(ctx.scope, digest_of({"query": selector.model_dump()}),
                         answer.snapshot.knowledge_seq, answer.snapshot.valid_at, answer)
        self._pack = pack
        return pack

    def current_pack(self, ctx: AuthorizedContext, selector: Selector) -> VoicePack | None:
        if not self.cfg.voice_v3_enabled or self._pack is None:
            return None
        if self._pack.scope != ctx.scope:
            return None
        if self._pack.query_digest != digest_of({"query": selector.model_dump()}):
            return None
        return self._pack
