"""Structured selectors: authorize before fetching any candidate or evidence."""
from __future__ import annotations

from ..auth.context import authorize
from ..contracts import Action, AuthorizedContext, Selector
from ..errors import AmbiguousIdentity, Malformed


def parse_selector(ctx: AuthorizedContext, selector: Selector) -> Selector:
    """Validate scope and predicates; missing qualifiers remain ambiguous."""
    if selector.scope != ctx.scope:
        raise Malformed("selector scope does not match authorized scope")
    authorize(ctx, predicate=selector.predicate or "*", action=Action.QUERY)
    if selector.fact_id and selector.predicate == "":
        raise AmbiguousIdentity("fact id selector requires a predicate for authorization")
    return selector


def missing_qualifiers(selector: Selector, required: tuple[str, ...]) -> tuple[str, ...]:
    present = {k for k, _ in selector.qualifiers}
    return tuple(q for q in required if q not in present)
