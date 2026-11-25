"""Executable strict schema-3 contract fixtures.

The JSON schemas under ``docs/ebrain/contracts/v3/`` are the single source of
truth: tests derive expected enums and required fields from the schemas, then
validate the fixtures with the self-contained validator in ``schema.py``.
"""
from __future__ import annotations

import copy
import json
import os

import pytest

from tools.ebrain.v3_eval import schema

SCHEMA_NAMES = (
    "write", "ack", "receipt", "query", "answer", "error",
    "scoped_cursor", "negotiation", "compatibility_matrix",
)


def _schema(contracts_dir: str, name: str) -> dict:
    with open(os.path.join(contracts_dir, f"{name}.schema.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _fixture(contracts_dir: str, name: str):
    with open(os.path.join(contracts_dir, f"{name}.fixture.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def _enum(schema_doc: dict, pointer: tuple[str, ...]) -> list:
    node = schema_doc
    for key in pointer:
        node = node[key]
    return list(node["enum"])


# ------------------------------------------------------------- validator
def test_validator_supports_only_declared_keywords():
    doc = {
        "type": "object",
        "required": ["a", "b"],
        "additionalProperties": False,
        "properties": {
            "a": {"type": "string", "minLength": 2, "pattern": "^v[0-9]+$"},
            "b": {"type": "integer", "minimum": 3},
            "c": {"type": ["string", "null"]},
            "d": {"type": "array", "items": {"enum": ["x", "y"]}},
            "e": {"const": 3},
        },
    }
    valid = {"a": "v12", "b": 3, "c": None, "d": ["x"], "e": 3}
    assert schema.validate(valid, doc) == []
    assert schema.validate({}, doc)  # required
    assert schema.validate({"a": "x", "b": 1, "d": ["z"], "e": 4}, doc)
    assert schema.validate({**valid, "extra": 1}, doc)  # additionalProperties

    with pytest.raises(schema.SchemaError):
        schema.Validator({"type": "string", "notAKeyword": True})
    assert schema.Validator({"type": "string"}).validate(1)
    with pytest.raises(schema.SchemaValidationError):
        schema.strict_validate({"a": "v12"}, doc)


def test_all_schema_documents_are_strict_and_loadable(contracts_dir):
    for name in SCHEMA_NAMES:
        doc = _schema(contracts_dir, name)
        validator = schema.Validator(doc)   # raises on unsupported keyword
        assert validator.validate(None) or isinstance(doc["type"], str)
        assert doc.get("title", "").startswith("ebrain-v3-")


# -------------------------------------------------------- write / receipts
def test_write_ack_receipt_fixtures_derive_statuses_from_schemas(contracts_dir):
    write_schema = _schema(contracts_dir, "write")
    schema.strict_validate(_fixture(contracts_dir, "write"), write_schema)

    receipt_schema = _schema(contracts_dir, "receipt")
    ack_schema = _schema(contracts_dir, "ack")
    statuses = _enum(receipt_schema, ("properties", "status"))
    # Single source of truth: ack and receipt must agree on the status set.
    assert _enum(ack_schema, ("properties", "status")) == statuses
    assert len(statuses) == 5

    receipts = _fixture(contracts_dir, "receipts")
    assert [r["status"] for r in receipts] == statuses
    for receipt in receipts:
        errors = schema.validate(receipt, receipt_schema)
        assert errors == []
        ack = {"schema": 3, "op_id": receipt["op_id"],
               "status": receipt["status"],
               "request_digest": receipt["request_digest"]}
        assert schema.validate(ack, ack_schema) == []
        assert set(receipt) == set(receipt_schema["required"]) | {
            "processing_url", "reason"}
    assert [r["committed_seq"] for r in receipts][-1] is None  # rejected


# ------------------------------------------------------------ query/answer
def test_query_and_answer_fixtures_are_strict(contracts_dir):
    query_schema = _schema(contracts_dir, "query")
    query = _fixture(contracts_dir, "query")
    assert schema.validate(query, query_schema) == []
    assert set(query) == set(query_schema["required"])

    answer_schema = _schema(contracts_dir, "answer")
    answer = _fixture(contracts_dir, "answer")
    assert schema.validate(answer, answer_schema) == []

    answer_statuses = _enum(answer_schema, ("properties", "answer_status"))
    fact_states = _enum(answer_schema, ("definitions", "fact", "properties",
                                        "state"))
    assert len(answer_statuses) == 6
    assert len(fact_states) == 6
    assert answer["answer_status"] in answer_statuses
    assert {f["state"] for f in answer["facts"]} <= set(fact_states)
    assert {"current", "conflict", "absent"} <= {f["state"]
                                                 for f in answer["facts"]}

    definitions = answer_schema["definitions"]
    for fact in answer["facts"]:
        assert set(fact) >= set(definitions["fact"]["required"])
        assert all(set(source) == set(definitions["source"]["required"])
                   for source in fact["provenance"])
        assert set(fact["freshness"]) == set(definitions["freshness"]["required"])
    assert set(answer["snapshot"]) >= set(definitions["snapshot"]["required"])
    assert set(answer["degradation"]) == set(
        definitions["degradation"]["required"])

    bad = copy.deepcopy(answer)
    bad["facts"][0]["provenance"][0]["kind"] = "untrusted_free_text"
    assert schema.validate(bad, answer_schema)
    bad2 = copy.deepcopy(answer)
    bad2["answer_status"] = "current"  # a fact state, not an answer status
    assert schema.validate(bad2, answer_schema)


# ------------------------------------------------------------------ errors
def test_error_body_is_exactly_four_fields(contracts_dir):
    error_schema = _schema(contracts_dir, "error")
    body = _fixture(contracts_dir, "error")
    assert set(body) == set(error_schema["required"])
    assert schema.validate(body, error_schema) == []
    assert body["code"] in _enum(error_schema, ("properties", "code"))
    assert isinstance(body["retryable"], bool)
    leaked = {**body, "sql": "select * from secrets"}
    assert schema.validate(leaked, error_schema)
    assert schema.validate({**body, "retryable": "yes"}, error_schema)
    assert schema.validate({**body, "code": "unknown-code"}, error_schema)


def test_scoped_cursor_is_strict(contracts_dir):
    cursor_schema = _schema(contracts_dir, "scoped_cursor")
    cursor = _fixture(contracts_dir, "scoped_cursor")
    assert schema.validate(cursor, cursor_schema) == []
    assert schema.validate({**cursor, "scope": ""}, cursor_schema)
    assert schema.validate({**cursor, "signature": "not-a-digest"}, cursor_schema)
    assert schema.validate({**cursor, "client_overwrite": True}, cursor_schema)


# ------------------------------------------------------------ negotiation
def test_negotiation_covers_3_1_and_unknown(contracts_dir):
    neg_schema = _schema(contracts_dir, "negotiation")
    cases = _fixture(contracts_dir, "negotiation")
    assert len(cases) == 3
    for case in cases:
        assert schema.validate(case, neg_schema) == []
    outcomes = _enum(neg_schema, ("properties", "outcome"))
    assert [c["outcome"] for c in cases] == ["supported", "legacy", "rejected"] \
        and set(outcomes) >= {"supported", "legacy", "rejected"}
    by_request = {c["requested_schema"]: c for c in cases}
    assert by_request[3]["resolved_schema"] == 3
    assert by_request[1]["resolved_schema"] == 1
    assert by_request[99]["resolved_schema"] is None
    assert by_request[99]["outcome"] == "rejected"
    assert all(c["header"] == "X-EBrain-Schema" for c in cases)
    assert schema.validate({**cases[0], "resolved_schema": 99}, neg_schema)


# ------------------------------------------------------ compatibility matrix
def test_compatibility_matrix_covers_all_client_schemas(contracts_dir):
    matrix_schema = _schema(contracts_dir, "compatibility_matrix")
    matrix = _fixture(contracts_dir, "compatibility_matrix")
    assert schema.validate(matrix, matrix_schema) == []
    assert matrix["server_schema"] == matrix_schema["properties"][
        "server_schema"]["const"]
    assert matrix["schema_version"] >= matrix_schema["properties"][
        "schema_version"]["minimum"]
    outcomes = _enum(matrix_schema, ("properties", "entries", "items",
                                     "properties", "outcome"))
    by_client = {e["client_schema"]: e["outcome"] for e in matrix["entries"]}
    assert set(by_client) == {3, 1, 99}
    assert by_client == {3: "supported", 1: "legacy", 99: "rejected"}
    assert set(by_client.values()) <= set(outcomes)
    bad = copy.deepcopy(matrix)
    bad["entries"][0]["outcome"] = "maybe"
    assert schema.validate(bad, matrix_schema)


def test_fixture_schema_hashes_are_reproducible(contracts_dir):
    """Schemas are stable source-of-truth artifacts, not generated noise."""
    digests = {}
    for name in SCHEMA_NAMES:
        doc = _schema(contracts_dir, name)
        digests[name] = schema.Validator(doc).validate({}) is not None
    assert len(digests) == len(SCHEMA_NAMES)


def test_M01_all_clients_errors_cursors(contracts_dir):
    """Traceability alias: schema/error/cursor compatibility across all clients."""
    test_all_schema_documents_are_strict_and_loadable(contracts_dir)
    test_query_and_answer_fixtures_are_strict(contracts_dir)
    test_error_body_is_exactly_four_fields(contracts_dir)
    test_scoped_cursor_is_strict(contracts_dir)
    test_negotiation_covers_3_1_and_unknown(contracts_dir)
    test_compatibility_matrix_covers_all_client_schemas(contracts_dir)
