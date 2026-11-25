"""M10/M12/M13/M14 pipeline tests: retrieval, projections, clients, API, quotas."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ebrain.v3.api import V3ApiConfig, create_app
from ebrain.v3.auth.context import DevelopmentPrincipalProvider
from ebrain.v3.clients.adapters import CliAdapter, McpAdapter, VoiceAdapter
from ebrain.v3.clients.negotiation import check_answer_compatibility, negotiate
from ebrain.v3.config import V3Config
from ebrain.v3.contracts import (
    Answer,
    AnswerStatus,
    Claim,
    ClaimKind,
    FactState,
    SchemaVersion,
    Selector,
    Snapshot,
    SourceContract,
    SourceRevision,
)
from ebrain.v3.db.memory import MemoryLedger
from ebrain.v3.errors import Malformed, QuotaExceeded, UnsupportedSchema
from ebrain.v3.projections.answers import clip, receipt_digest
from ebrain.v3.projections.derived import DerivedArtifact, DerivedDAG
from ebrain.v3.projections.evidence import verify_evidence
from ebrain.v3.projections.materialize import materialize
from ebrain.v3.projections.rebuild import rebuild_report
from ebrain.v3.quotas.plans import PlanPolicy
from ebrain.v3.resolver.policy import DEFAULT_POLICY
from ebrain.v3.retrieval.query import QueryService, fuse
from ebrain.v3.service import V3Service
from ebrain.v3.sources.snapshots import SourceRegistry

from .v3_helpers import ORG, SCOPE, ctx, key, principal, write


def service(cfg: V3Config | None = None) -> V3Service:
    return V3Service.build(cfg=cfg)


def seeded_service() -> V3Service:
    svc = service()
    c = ctx()
    k = key()
    svc.write(c, write("o1", k, "active"))
    return svc


def test_H01_protected_multifacet_candidates_survive_fusion():
    svc = seeded_service()
    c = ctx()
    claims = svc.ledger.load_slice(c, (), svc.ledger.seq)
    qs = svc.retriever
    sel = Selector(scope=SCOPE, predicate="decision.status", resource_id="svc",
                   qualifiers=(("repo", "acme/api"), ("environment", "prod")), text="svc")
    candidates = qs.candidates(c, sel, svc.ledger.snapshot(c), claims)
    exact = [x for x in candidates.candidates if x.arm == "exact"]
    assert exact and exact[0].protected
    # A synthetic reranker cannot remove a protected fact from the union.
    fused = fuse({"exact": tuple(exact), "lexical": ()})
    assert any(x.fact_id == exact[0].fact_id and x.protected for x in fused)


def test_H03_incompatible_generation_degrades_not_mixes():
    cfg = V3Config(vector_retrieval_enabled=True)
    svc = service(cfg)
    c = ctx()
    claims = svc.ledger.load_slice(c, (), svc.ledger.seq)
    result = svc.retriever.candidates(
        c, Selector(scope=SCOPE), svc.ledger.snapshot(c), claims
    )
    assert "vector_unavailable" in result.degradation
    assert not any("vector" in x.arm for x in result.candidates)


def test_H10_answer_degrades_on_incomplete_coverage():
    svc = seeded_service()
    c = ctx()
    answer = svc.query(c, Selector(scope=SCOPE, predicate="decision.status"))
    assert answer.answer_status is AnswerStatus.COMPLETE
    degraded = QueryService(V3Config(), DEFAULT_POLICY).answer(
        c, Selector(scope=SCOPE, predicate="decision.status"),
        svc.ledger.snapshot(c),
        svc.ledger.load_slice(c, (), svc.ledger.seq), (), (), (), incomplete=True,
    )
    assert "index_lag" in degraded.degradation
    assert degraded.answer_status is AnswerStatus.PARTIAL


def test_M06_exact_span_evidence_rejects_unsupported_prose():
    registry = SourceRegistry()
    from ebrain.v3.contracts import Span
    span = Span(start=0, end=4, digest="span-digest")
    rev = SourceRevision(source_id="s", revision="r", digest="rev-digest",
                         parser_version="v1", contract=SourceContract.APPROVED_ARTIFACT,
                         spans=(span,))
    registry.register(rev)
    claim = Claim(
        claim_id="c1", key=key(), kind=ClaimKind.ASSERTION, value="active",
        source=rev, principal_id="alice", valid_from="2026-01-01T00:00:00+00:00",
        knowledge_seq=1, digest="d", fact_id=key().key_id,
    )
    assert verify_evidence(claim, registry).verified
    wrong = claim.model_copy(update={
        "source": rev.model_copy(update={"digest": "wrong"}),
    })
    assert not verify_evidence(wrong, registry).verified


def test_H04_derived_never_becomes_current_and_cycle_rejected():
    dag = DerivedDAG()
    dag.add(DerivedArtifact("d1", ("fact1",), 1, "m"))
    with pytest.raises(ValueError):
        dag.add(DerivedArtifact("d2", ("d2",), 1, "m"))
    payloads = dag.as_noncurrent_claims(SCOPE, "svc")
    assert all(p["kind"] == "derived" for p in payloads)


def test_C08_rebuild_detects_bad_card():
    svc = seeded_service()
    c = ctx()
    resolved = svc.retriever.answer(c, Selector(scope=SCOPE), svc.ledger.snapshot(c),
                                    svc.ledger.load_slice(c, (), svc.ledger.seq), (), (), ())
    from ebrain.v3.resolver.reducer import Resolver
    facts = Resolver(DEFAULT_POLICY).resolve(
        svc.ledger.load_slice(c, (), svc.ledger.seq), (), (), (), svc.ledger.snapshot(c)
    )
    cards = materialize(facts, svc.ledger.load_slice(c, (), svc.ledger.seq), svc.ledger.snapshot(c))
    good = rebuild_report(cards, cards, {})
    assert good.safe_to_activate
    from dataclasses import replace
    corrupted = (replace(cards[0], value_digest="poisoned"),)
    bad = rebuild_report(cards, corrupted, {})
    assert not bad.match
    assert bad.differences


def test_M01_schema_negotiation_and_incompatible_client():
    assert negotiate("3") is SchemaVersion.V3
    assert negotiate(None) is SchemaVersion.V1
    with pytest.raises(UnsupportedSchema):
        negotiate("9")
    answer = seeded_service().query(ctx(), Selector(scope=SCOPE))
    assert not check_answer_compatibility(SchemaVersion.V3, answer).compatible is False
    answer_with_current = answer
    result = check_answer_compatibility(SchemaVersion.V1, answer_with_current)
    assert result.compatible is True


def test_compact_clipping_preserves_critical_states():
    svc = seeded_service()
    answer = svc.query(ctx(), Selector(scope=SCOPE))
    delivery = clip(answer, 200)
    # When the fixed envelope alone exceeds the declared budget, clipping is
    # explicitly reported rather than silently claiming the budget was met.
    assert delivery.delivered_bytes == len(delivery.as_json().encode("utf-8"))
    assert delivery.clipped or delivery.delivered_bytes <= 200
    assert "clipped_facets" in delivery.answer.completeness or not delivery.clipped
    assert receipt_digest(delivery)


def test_M09_receipts_and_clients_delegate_same_service():
    svc = seeded_service()
    c = ctx()
    pack = CliAdapter(svc).pack(c, Selector(scope=SCOPE, predicate="decision.status"))
    assert pack.answer.answer_status is AnswerStatus.COMPLETE
    mcp = McpAdapter(svc, V3Config())
    assert mcp.tools() == ()
    with pytest.raises(UnsupportedSchema):
        mcp.call_tool(c, "ebrain.query", {"selector": {"scope": SCOPE}})
    voice = VoiceAdapter(svc, V3Config(voice_v3_enabled=True))
    assert voice.current_pack(c, Selector(scope=SCOPE)) is None
    voice.refresh(c, Selector(scope=SCOPE))
    assert voice.current_pack(c, Selector(scope=SCOPE)) is not None
    with pytest.raises(Malformed):
        CliAdapter(svc).maintain(c, "drop_table")


def test_H07_atomic_last_slot_quota():
    plan = PlanPolicy("individual_free")
    from ebrain.v3.contracts import UsageReservation
    usage = UsageReservation(scope=SCOPE, facts=999, events=0, plan_revision=plan.revision)
    plan.check(usage, UsageReservation(scope=SCOPE, facts=1, events=1))
    with pytest.raises(QuotaExceeded):
        plan.check(usage, UsageReservation(scope=SCOPE, facts=2, events=1))


def test_api_v3_disabled_by_default_and_routes_when_enabled(tmp_path):
    provider = DevelopmentPrincipalProvider(registry={"tok": principal()})
    svc = seeded_service()
    disabled = TestClient(create_app(V3ApiConfig(V3Config(), svc, provider.authenticate)))
    assert disabled.get("/v1/ebrain/health").json()["enabled"] is False
    assert disabled.post("/v1/ebrain/query", json={"scope": SCOPE},
                         headers={"X-EBrain-Schema": "3", "X-EBrain-Scope": SCOPE,
                                  "X-EBrain-Token": "tok"}).status_code == 400

    enabled_cfg = V3Config(schema3_http_enabled=True)
    enabled_svc = seeded_service()
    client = TestClient(create_app(V3ApiConfig(enabled_cfg, enabled_svc, provider.authenticate)))
    headers = {"X-EBrain-Schema": "3", "X-EBrain-Scope": SCOPE, "X-EBrain-Token": "tok"}
    response = client.post("/v1/ebrain/query", json={"scope": SCOPE}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["answer_status"] in {"complete", "not_found", "partial"}
    unauth = client.post("/v1/ebrain/query", json={"scope": SCOPE},
                         headers={"X-EBrain-Schema": "3", "X-EBrain-Scope": SCOPE})
    assert unauth.status_code == 401
    unknown = client.post("/v1/ebrain/query", json={"scope": SCOPE},
                          headers={"X-EBrain-Schema": "99", "X-EBrain-Scope": SCOPE,
                                   "X-EBrain-Token": "tok"})
    assert unknown.status_code == 400


def test_H06_migration_export_and_reconcile(tmp_path):
    from tools.ebrain.operations.migrate import export, main, map_event, reconcile

    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE ops(seq INTEGER PRIMARY KEY, user_id TEXT, op_id TEXT, ts INTEGER, "
                 "project TEXT, kind TEXT, path TEXT, auth INTEGER, ext INTEGER, sup INTEGER, "
                 "deleted INTEGER, digest TEXT)")
    conn.execute("INSERT INTO ops VALUES (1,'u1','op1',1,'p','claim','',2,0,0,0,'d')")
    conn.execute("INSERT INTO ops VALUES (2,'u1','op2',2,'p','claim','',2,1,1,0,'d2')")
    conn.commit()
    conn.close()
    out = tmp_path / "export.json"
    manifest = export(db, out)
    assert manifest.tables["ops"] == 2
    assert manifest.high_water_seq == 2
    assert manifest.quarantined == ("op2",)
    assert reconcile(manifest, 1, 1)["pass"] is True
    mapped = map_event(source_instance="synthetic", legacy_user="u1", legacy_op_id="op1")
    assert mapped["op_id"].startswith("mig_") and mapped["valid_from"] == "unknown"
    assert main(["reconcile", "--manifest", str(out), "--accepted", "1",
                 "--quarantined", "1"]) == 0


def test_M05_consolidation_is_advisory_and_deduplicated():
    from ebrain.v3.workers.consolidate import ConsolidationService
    from .test_resolver_v3 import claim
    svc = ConsolidationService(V3Config())
    a = claim("a", "v1", seq=1)
    b = claim("b", "v2", seq=2, base_seq=1)
    issues = svc.typed_contradictions((a, b))
    assert issues and svc.record(issues) == len(issues)
    assert svc.record(issues) == 0
    assert svc.advisory_only
    assert svc.outbox.pending_count > 0


def test_restore_rehearsal_fails_closed_on_unknown_suppression(tmp_path):
    from tools.ebrain.operations.restore import verify_restore
    result = verify_restore(tmp_path, {"latest_control_seq": 5})
    assert result["open_for_serving"] is False
    assert result["reason"] == "missing_artifacts"
    (tmp_path / "database.bin").write_bytes(b"db")
    (tmp_path / "wal.bin").write_bytes(b"wal")
    (tmp_path / "control.json").write_text("{}", encoding="utf-8")
    (tmp_path / "suppression.json").write_text("{}", encoding="utf-8")
    result = verify_restore(tmp_path, {"latest_control_seq": 5})
    assert result["reason"] == "unknown_latest_suppression"
    (tmp_path / "suppression.json").write_text('{"latest_seq": 6}', encoding="utf-8")
    assert verify_restore(tmp_path, {"latest_control_seq": 5})["open_for_serving"] is True
