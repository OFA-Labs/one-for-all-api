"""Honest answer assembly and budget-safe compact clipping (CP12.5)."""
from __future__ import annotations

from dataclasses import dataclass

from ..contracts import Answer, AnswerItem, AnswerStatus, FactState, digest_of

CRITICAL_STATES = frozenset({
    FactState.CONFLICT, FactState.PENDING_VERIFICATION, FactState.WITHDRAWN,
    FactState.UNKNOWN, FactState.ABSENT,
})


@dataclass(frozen=True)
class Delivery:
    answer: Answer
    delivered_bytes: int
    clipped: tuple[str, ...]

    def as_json(self) -> str:
        import json
        return json.dumps(self.answer.model_dump(mode="json"), sort_keys=True,
                          separators=(",", ":"))


def clip(answer: Answer, budget_bytes: int) -> Delivery:
    """Reserve room for scope/state/conflict/pending/critical evidence first."""
    full = answer.model_dump(mode="json")
    raw = __import__("json").dumps(full, sort_keys=True, separators=(",", ":"))
    if len(raw.encode("utf-8")) <= budget_bytes:
        return Delivery(answer, len(raw.encode("utf-8")), ())

    critical = [i for i in answer.items if i.state in CRITICAL_STATES]
    ordinary = [i for i in answer.items if i.state not in CRITICAL_STATES]
    kept: list[AnswerItem] = list(critical)
    clipped: list[str] = []
    size = len(__import__("json").dumps(
        answer.model_copy(update={"items": tuple(kept)}).model_dump(mode="json"),
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8"))
    for item in ordinary:
        candidate = kept + [item]
        trial = len(__import__("json").dumps(
            answer.model_copy(update={"items": tuple(candidate)}).model_dump(mode="json"),
            sort_keys=True, separators=(",", ":"),
        ).encode("utf-8"))
        if trial <= budget_bytes:
            kept.append(item)
            size = trial
        else:
            clipped.append(item.fact_id)
    degraded = tuple(dict.fromkeys((*answer.degradation, "compacted")))
    status = answer.answer_status
    if clipped and status is AnswerStatus.COMPLETE:
        status = AnswerStatus.PARTIAL
    delivered = answer.model_copy(update={
        "items": tuple(kept), "degradation": degraded,
        "answer_status": status,
        "completeness": (*answer.completeness, "clipped_facets"),
    })
    import json
    actual = len(json.dumps(
        delivered.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8"))
    return Delivery(delivered, actual, tuple(clipped))


def receipt_digest(delivery: Delivery) -> str:
    return digest_of({
        "payload": delivery.delivered_bytes,
        "snapshot": delivery.answer.snapshot.knowledge_seq,
        "request": delivery.answer.request_id,
        "clipped": list(delivery.clipped),
    })
