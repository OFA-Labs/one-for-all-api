"""OFA's agent, built as LangGraph graphs. Diagrams: docs/ofa/GRAPHS.md (scripts/draw_graphs.py).

    turn      one utterance → control or brain                          (turn.py)
    brain     engine ↔ tools loop, spoken report                        (brain.py)
    hands     the policy gate: tier → approval → effect → ledger/audit  (hands.py)
    approval  spoken yes/no for one exact action                        (approval.py)

Questions to the user are interrupt()s (pauses.py); runner.py speaks them and resumes with the answer.
Rules (tiers, lexicon, vault, screen readers) are plain modules the nodes call, so they stay testable alone.
"""
from .report import TurnResult, tidy
from .runner import Runner

__all__ = ["Runner", "TurnResult", "tidy"]
