from __future__ import annotations

import pytest

from voice.websites import WebsiteResolver, validate_url


@pytest.mark.parametrize("value", ["javascript:alert(1)", "file:///C:/secret", "https://user:pass@example.com",
                                    "https://example.com\nopen calc", "https://example.com\\evil"])
def test_unsafe_urls_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        validate_url(value)


def test_websites_bookmarks_and_encoded_search() -> None:
    resolver = WebsiteResolver({"my repo": "https://github.com/ofa/project"})
    assert resolver.resolve("open YouTube") == ("website.open", "https://www.youtube.com")
    assert resolver.resolve("go to github.com") == ("website.open", "https://github.com")
    assert resolver.resolve("open my repo") == ("website.open", "https://github.com/ofa/project")
    assert resolver.resolve("open my unknown repo") is None
    assert resolver.resolve("search for LangGraph & Python on Google") == (
        "web.search", "https://www.google.com/search?q=LangGraph+%26+Python")
