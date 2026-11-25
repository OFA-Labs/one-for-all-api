"""Traceability: M09."""
from __future__ import annotations

import json

import pytest

from ebrain.v3.clients.adapters import CliAdapter, VoiceAdapter
from ebrain.v3.contracts import AnswerStatus, Selector
from ebrain.v3.config import V3Config

from .test_pipeline_v3 import seeded_service
from .v3_helpers import SCOPE, ctx


def test_M09_receipt_transport_and_feedback():
    svc = seeded_service()
    c = ctx()
    pack = CliAdapter(svc).pack(c, Selector(scope=SCOPE, predicate="decision.status"))
    assert pack.answer.answer_status is AnswerStatus.COMPLETE
    assert pack.answer.receipts == ()
    voice = VoiceAdapter(svc, V3Config(voice_v3_enabled=True))
    selector = Selector(scope=SCOPE)
    voice.refresh(c, selector)
    pack2 = voice.current_pack(c, selector)
    assert pack2 is not None and pack2.snapshot_seq == svc.ledger.seq
    # Delivery does not prove the client followed a fact, and a stale selector
    # never yields the pack as current.
    assert voice.current_pack(c, Selector(scope=SCOPE, predicate="owner.assignment")) is None


def test_mcp_server_delegates_to_shared_service():
    from ebrain.v3.config import V3Config
    from ebrain.v3.errors import Malformed, UnsupportedSchema
    from ebrain.v3.mcp import McpServer

    svc = seeded_service()
    disabled = McpServer(svc)
    assert disabled.tools() == {}
    with pytest.raises(UnsupportedSchema):
        disabled.dispatch(ctx(), "ebrain.query", {"scope": SCOPE})
    enabled = McpServer(svc, V3Config(mcp_enabled=True))
    assert "ebrain.query" in enabled.tools()
    answer = enabled.dispatch(ctx(), "ebrain.query", {"scope": SCOPE})
    assert answer.answer_status is AnswerStatus.COMPLETE
    with pytest.raises(Malformed):
        enabled.dispatch(ctx(), "ebrain.query", {"scope": "x; DROP TABLE y"})


def test_voice_v3_pack_never_speaks_guessed_current():
    from ebrain.v3.contracts import AnswerStatus, Selector
    from ebrain.voice_client import EBrainV3PackClient

    svc = seeded_service()
    answer = svc.query(ctx(), Selector(scope=SCOPE))
    pack = EBrainV3PackClient.render(answer)
    assert "current:" in pack
    assert "evidence=" in pack
    client = EBrainV3PackClient(svc)
    assert client.refresh(ctx(), Selector(scope=SCOPE))
    unconfigured = EBrainV3PackClient()
    assert unconfigured.refresh(ctx(), Selector(scope=SCOPE)) == ""


def test_schema3_cli_is_additive_and_opt_in(capsys):
    from ebrain.v3.cli import main as cli_main

    assert cli_main(["limits"]) == 3
    assert "incompatible_client" in capsys.readouterr().out
    assert cli_main(["--enable-v3-local", "limits"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["price"] is None
    assert cli_main([
        "--enable-v3-local", "remember", "--op-id", "cli1",
        "--resource-id", "svc", "--value", "active",
    ]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "applied"
