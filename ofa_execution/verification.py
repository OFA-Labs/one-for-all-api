"""Readback assertions, independent from whether an input call returned."""
from .contracts import Evidence, Outcome


def verify(step, before, after):
    expected = step.expect
    good = False
    if expected:
        if expected.kind == "changed":
            good = before.hash != after.hash
        elif expected.kind == "url":
            good = after.facts.get("url") == expected.value
        elif expected.kind == "value":
            good = any(e.value == expected.value and (not step.target.name or e.name == step.target.name)
                       for e in after.elements if not e.protected)
        elif expected.kind == "text":
            good = any(expected.value in (e.name + " " + (e.value or "")) for e in after.elements
                       if expected.value is not None and not e.protected)
    return Outcome(status="verified" if good else "unknown", observation=after,
                   evidence=[Evidence(tier="A", kind="fresh_surface_read", reading_hash=after.hash,
                                      detail={"assertion_matched": good})])
