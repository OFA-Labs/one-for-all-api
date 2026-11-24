"""T-090: the owner-approved E-Brain product-spec amendment ships in M1."""
from pathlib import Path


def test_spec_amended() -> None:
    spec = (
        Path(__file__).resolve().parents[2]
        / "one-for-all-web"
        / "docs"
        / "SPEC_ITERATION_1.md"
    ).read_text(encoding="utf-8")
    assert "intentionally blank placeholder" not in spec
    assert "**e-brain** shows the shared project memory (EXPERIMENTAL)" in spec
