"""Real speech rarely says a catalog name perfectly; keep resolution bounded."""
from voice.intent import Router
from voice.websites import WebsiteResolver


def router():
    apps = {
        "WhatsApp": ["whats app"],
        "Slack": ["slack app"],
        "Visual Studio Code": ["vs code", "v s code", "vscode", "code editor"],
        "Claude Code": ["claude code cli"],
        "Claude": ["claude desktop"],
    }
    aliases = [(alias, name) for name, variants in apps.items()
               for alias in [name, *variants]]
    return Router(aliases, "auto", {})


def test_polite_suffix_and_spoken_word_splitting_still_open_apps():
    r = router()
    assert r.route("open Slack please").slots == {"app": "Slack"}
    assert r.route("please open Slack").slots == {"app": "Slack"}
    assert r.route("open V S Code").slots == {"app": "Visual Studio Code"}
    assert r.route("open VSCode please").slots == {"app": "Visual Studio Code"}


def test_misspellings_only_suggest_and_never_auto_launch():
    r = router()
    for phrase in ("open slak", "open watsapp", "open clawed code", "open black",
                   "open random thing"):
        intent = r.route(phrase)
        assert intent.intent == "clarify"
        assert not intent.actions
    assert "Slack" in r.route("open slak").slots.get("suggestions", "")


def test_common_website_names_and_polite_suffixes_resolve():
    sites = WebsiteResolver()
    assert sites.resolve("open google") == ("website.open", "https://www.google.com")
    assert sites.resolve("open github please") == ("website.open", "https://github.com")
    assert sites.resolve("go to example dot com please") == (
        "website.open", "https://example.com")
