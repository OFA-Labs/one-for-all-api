"""Pure resolver result types and conversion to the wire answer contract."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts import AnswerItem, FactKey, FactState, Provenance, Snapshot


@dataclass(frozen=True)
class ResolvedFact:
    key: FactKey
    fact_id: str
    state: FactState
    value: Any = None
    value_type: str = "scalar"
    provenance: tuple[Provenance, ...] = ()
    annotations: tuple[str, ...] = ()
    freshness: str = "unknown"
    representative_claim_id: str = ""
    equivalent_codes: tuple[str, ...] = ()

    def to_answer_item(self, confidence: float = 1.0) -> AnswerItem:
        return AnswerItem(
            fact_id=self.fact_id or self.key.key_id,
            key=self.key,
            state=self.state,
            current_value=self.value if self.state is FactState.CURRENT else None,
            value_type=self.value_type,
            confidence=confidence if self.state is FactState.CURRENT else 0.0,
            provenance=self.provenance,
            annotations=self.annotations,
            freshness=self.freshness,
        )
