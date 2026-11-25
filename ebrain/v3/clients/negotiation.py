"""Explicit schema negotiation. V3 is never inferred from an unknown field."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..contracts import Answer, AnswerStatus, SchemaVersion
from ..errors import UnsupportedSchema

SUPPORTED: Final[frozenset[int]] = frozenset({1, 3})


def negotiate(header: str | None) -> SchemaVersion:
    if header is None or header.strip() == "":
        return SchemaVersion.V1
    try:
        value = int(header.strip())
    except ValueError as exc:
        raise UnsupportedSchema("unknown E-Brain schema") from exc
    if value not in SUPPORTED:
        raise UnsupportedSchema(f"unsupported E-Brain schema: {value}")
    return SchemaVersion(value)


@dataclass(frozen=True)
class CompatibilityResult:
    compatible: bool
    reason: str


def check_answer_compatibility(version: SchemaVersion, answer: Answer) -> CompatibilityResult:
    """A schema-1 client cannot represent unsafe state; reject, never flatten."""
    if version is SchemaVersion.V3:
        return CompatibilityResult(True, "")
    unsafe = [i for i in answer.items if i.state.value not in ("current", "absent")]
    if unsafe:
        return CompatibilityResult(
            False,
            "schema-1 client cannot represent conflict/pending/withdrawn/unknown state",
        )
    if answer.answer_status not in (AnswerStatus.COMPLETE, AnswerStatus.NOT_FOUND):
        return CompatibilityResult(False, "schema-1 client cannot represent degraded answers")
    return CompatibilityResult(True, "")
