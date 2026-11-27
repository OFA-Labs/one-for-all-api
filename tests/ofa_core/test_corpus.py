"""Info Corpus: open documents become small relevant facts; private items are never returned."""
import io

import pytest
from fastapi.testclient import TestClient

from ofa.config import OfaConfig
from ofa.corpus import OpenCorpus
from ofa.engine.fake import FakeEngine
from ofa.harness.api import Harness
from ofa.harness.fake import FakeDesktop
from ofa.runtime import build_core
from voice.api import create_app
from voice.config import Settings
from voice.events import Events

ORIGIN = "http://127.0.0.1:3000"
RESUME = """# Resume

## Contact
- Full name: Asha Rao
- Email: asha@example.test

## Experience

### ML Intern at Example Co
- Dates: Jan 2026 - Mar 2026
- Built an evaluation harness.

## Certifications
- AWS Academy Graduate (Mar 2026)
"""


def test_documents_become_facts_with_their_headings(tmp_path):
    corpus = OpenCorpus(tmp_path)
    corpus.write("resume", RESUME)
    facts = [f.public() for f in corpus.facts()]
    assert "[resume › Contact] Full name: Asha Rao" in facts
    assert "[resume › Experience › ML Intern at Example Co] Built an evaluation harness." in facts


def test_relevant_facts_fit_a_budget_and_match_the_question(tmp_path):
    corpus = OpenCorpus(tmp_path)
    corpus.write("resume", RESUME + "\n## Hobbies\n" + "\n".join(f"- hobby number {i} " + "x" * 80 for i in range(60)))
    picked = corpus.relevant(["Which certifications have you pursued?"], budget_chars=500)
    assert sum(len(f.public()) for f in picked) <= 500
    assert any("AWS Academy" in f.text for f in picked)


def test_bad_names_and_huge_documents_are_refused(tmp_path):
    corpus = OpenCorpus(tmp_path)
    for name in ("../secrets", "a/b", "", "x" * 80):
        with pytest.raises(ValueError):
            corpus.write(name, "x")
    with pytest.raises(ValueError):
        corpus.write("big", "x" * 300_000)
    corpus.write("answers", "# Answers")
    corpus.append("answers", "Foreign languages", "Nil")
    assert "## Foreign languages\nNil" in corpus.read("answers") and corpus.delete("answers")


class Yes:
    def verify(self, reason):
        return True


class Pairing:
    def authorize(self, origin, token):
        if token != "paired":
            raise PermissionError("not paired")
        return {}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("OFA_DATA_DIR", str(tmp_path))
    import ofa.vault.store as store
    monkeypatch.setattr(store, "dpapi_wrap", lambda k: k[::-1])
    monkeypatch.setattr(store, "dpapi_unwrap", lambda k: k[::-1])
    core = build_core(OfaConfig(engine="fake"), harness=Harness(FakeDesktop()), engine=FakeEngine(), verifier=Yes())
    core.vault._wrap, core.vault._unwrap = (lambda k: k[::-1]), (lambda k: k[::-1])
    session = type("S", (), {"brain": type("B", (), {"core": core})()})()
    app = create_app(Settings(), Events("fake", io.StringIO()), session, "x" * 48, Pairing())
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        def call(method, path, json=None, token="paired"):
            headers = {"origin": ORIGIN, "authorization": f"Bearer {token}"}
            return client.post(path, headers=headers, json=json or {}) if method == "post" \
                else client.get(path, headers=headers)
        yield call, core
    from ofa.egress import EGRESS
    EGRESS.forget_all()


def test_corpus_routes_need_pairing(api):
    call, _ = api
    assert call("get", "/v1/corpus/open", token="no").status_code == 403
    assert call("get", "/v1/corpus/private", token="no").status_code == 403


def test_save_a_resume_larger_than_the_normal_request_limit(api):
    call, core = api
    text = "# Resume\n" + "- fact\n" * 3000
    assert call("post", "/v1/corpus/open/save", {"name": "resume", "text": text}).status_code == 200
    assert call("get", "/v1/corpus/open").json()["documents"][0]["name"] == "resume"
    assert call("get", "/v1/corpus/open/resume").json()["text"] == text
    assert call("post", "/v1/corpus/open/delete", {"name": "resume"}).json()["deleted"]
    assert call("post", "/v1/corpus/open/save", {"name": "../x", "text": "y"}).status_code == 400


def test_private_values_go_in_but_never_come_out(api):
    call, core = api
    item = {"service": "gmail", "label": "password", "value": "Qq-Private-445566", "site": "https://accounts.google.com"}
    assert call("post", "/v1/corpus/private/add", item).json()["code"] == "VAULT_LOCKED"
    assert call("post", "/v1/corpus/private/unlock").json()["unlocked"]
    added = call("post", "/v1/corpus/private/add", item)
    assert added.status_code == 200 and "Qq-Private-445566" not in added.text
    handle = added.json()["items"][0]["handle"]
    assert "Qq-Private-445566" not in call("get", "/v1/corpus/private").text
    assert call("post", "/v1/corpus/private/add", {**item, "site": "http://evil"}).json()["code"] == "INVALID_ITEM"
    assert call("post", "/v1/corpus/private/delete", {"handle": handle}).json()["items"] == []
