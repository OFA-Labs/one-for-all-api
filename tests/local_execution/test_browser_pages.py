"""The page scripts in a real headless browser, on local fixture pages only.

Runs when Node and Playwright are available (set OFA_PLAYWRIGHT_DIR, or keep the
web repo next to this one). This exercises OFA's adapter and scripts, not the
pinned browse binary; see test_browser_real.py for that.
"""
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from ofa_execution.browser import BrowserHand
from ofa_execution.config import LocalConfig
from ofa_execution.contracts import Expectation, ExecutionError, Step, Target

ROOT = Path(__file__).resolve().parents[2]
PLAYWRIGHT = Path(os.environ.get("OFA_PLAYWRIGHT_DIR") or ROOT.parent / "one-for-all-web" / "node_modules")

pytestmark = pytest.mark.skipif(not (shutil.which("node") and (PLAYWRIGHT / "playwright").is_dir()),
                                reason="Needs Node and Playwright; set OFA_PLAYWRIGHT_DIR")

PAGES: dict[str, str] = {}


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAGES.get(self.path)
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((body or "").encode())

    def log_message(self, *args):
        pass


class HarnessClient:
    def __init__(self):
        self.process = subprocess.Popen(["node", str(Path(__file__).with_name("browser_page_harness.cjs"))],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        text=True, encoding="utf-8",
                                        env={**os.environ, "OFA_PLAYWRIGHT_DIR": str(PLAYWRIGHT)})
        first = self.process.stdout.readline()
        if '"ready"' not in first:
            self.close()
            pytest.skip("No headless browser could be started")

    def call(self, name, args):
        self.process.stdin.write(json.dumps({"name": name, "args": args}) + "\n")
        self.process.stdin.flush()
        reply = json.loads(self.process.stdout.readline())
        if "error" in reply:
            raise ExecutionError("BROWSER_ERROR", reply["error"])
        return reply["result"]

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()


@pytest.fixture(scope="module")
def site():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = HarnessClient()
    yield f"http://127.0.0.1:{server.server_port}", client
    client.close()
    server.shutdown()
    server.server_close()


def show(site, name, html, **limits):
    """Open a fixture page and return (hand, read) for it."""
    origin, client = site
    PAGES["/" + name] = "<!doctype html><title>" + name + "</title>" + html
    config = LocalConfig(fixture_origins=[origin], allowed_origins=[origin], **limits)
    hand = BrowserHand(config, client)
    client.call("navigate", {"url": origin + "/" + name})
    hand.tabs, hand.last_tab = {"1": origin}, "1"
    return hand, lambda: hand.observe(Step(operation="browser.observe"))


def click(hand, name, expected):
    step = Step(operation="browser.click", target=Target(name=name, role="button"),
                expect=Expectation(kind="text", value=expected))
    return hand.execute(step, hand.observe(step), lambda: None)


BUTTON = '<button onclick="document.querySelector(\'p\').textContent=\'clicked\'">Send</button><p>idle</p>'


def paragraph(reading):
    return next(e.name for e in reading.elements if e.role == "p")


def test_a_covered_button_is_not_clicked(site):
    banner = '<div style="position:fixed;inset:0;background:#000;opacity:.5">cookies</div>'
    hand, read = show(site, "covered", BUTTON + banner)
    with pytest.raises(ExecutionError) as error:
        click(hand, "Send", "clicked")
    assert error.value.code == "HIT_TARGET_INTERCEPTED"
    assert paragraph(read()) == "idle"


def test_a_moving_button_is_not_clicked(site):
    moving = ('<style>button{position:relative;animation:m .3s linear infinite alternate}'
              '@keyframes m{from{left:0}to{left:300px}}</style>')
    hand, read = show(site, "moving", moving + BUTTON)
    with pytest.raises(ExecutionError) as error:
        click(hand, "Send", "clicked")
    # The approved reading is already stale or the element is still moving; either way nothing is sent.
    assert error.value.code in {"ELEMENT_UNSTABLE", "READING_CHANGED"}
    assert paragraph(read()) == "idle"


def test_a_clear_button_below_the_fold_is_clicked_without_leaving_the_page_scrolled(site):
    hand, read = show(site, "below", '<div style="height:3000px"></div>' + BUTTON)
    before = read()
    outcome = click(hand, "Send", "clicked")
    assert outcome.status == "verified"
    button = lambda reading: next(e.bounds for e in reading.elements if e.role == "button")
    assert button(outcome.observation) == button(before)


def test_labels_children_and_shadow_free_controls_count_as_the_target(site):
    html = ('<button onclick="document.querySelector(\'p\').textContent=\'clicked\'">'
            '<span style="display:inline-block;width:200px">Send</span></button><p>idle</p>')
    hand, _ = show(site, "child", html)
    assert click(hand, "Send", "clicked").status == "verified"


def frame(name, html, host=""):
    PAGES["/" + name] = "<!doctype html><title>frame</title>" + html
    return f'<iframe src="{host}/{name}" style="width:500px;height:200px;margin-top:900px"></iframe>'


def named(reading, name):
    return next(e for e in reading.elements if e.name == name)


def test_same_origin_frames_are_read_and_usable(site):
    inner = BUTTON.replace("document.querySelector", "this.ownerDocument.querySelector") + (
        '<label for="m">Message</label><input id="m">')
    hand, read = show(site, "framed", frame("inner", inner))
    reading = read()
    assert reading.complete
    button = named(reading, "Send")
    assert button.ref.startswith("frame:1/") and button.bounds[1] > 900
    assert click(hand, "Send", "clicked").status == "verified"
    step = Step(operation="browser.fill", target=Target(name="Message", role="edit"), text="hello",
                expect=Expectation(kind="value", value="hello"))
    assert hand.execute(step, read(), lambda: None).status == "verified"


def test_a_banner_over_a_frame_blocks_the_click(site):
    banner = '<div style="position:fixed;inset:0">cookies</div>'
    hand, _ = show(site, "framed-covered", frame("covered-inner", BUTTON) + banner)
    with pytest.raises(ExecutionError) as error:
        click(hand, "Send", "clicked")
    assert error.value.code == "HIT_TARGET_INTERCEPTED"


def test_open_shadow_roots_are_read_and_usable(site):
    html = ('<div id="host"></div><script>const r=document.getElementById("host").attachShadow({mode:"open"});'
            'r.innerHTML=\'<button>Send</button><p>idle</p>\';'
            'r.querySelector("button").onclick=()=>r.querySelector("p").textContent="clicked";</script>')
    hand, read = show(site, "shadow", html)
    assert read().complete
    assert click(hand, "Send", "clicked").status == "verified"


def test_a_frame_from_another_origin_is_not_entered(site):
    other = site[0].replace("127.0.0.1", "localhost")
    _, read = show(site, "foreign", "<p>outer</p>" + frame("secret", "<button>Hidden</button>", other))
    reading = read()
    assert not reading.complete
    assert [e.name for e in reading.elements] == ["outer"]


def test_protected_fields_inside_a_frame_stay_masked(site):
    _, read = show(site, "login", frame("login-inner", '<input type="password" value="hunter2-canary">'))
    reading = read()
    assert reading.facts["human_required"]
    assert "hunter2-canary" not in reading.model_dump_json()
    assert next(e for e in reading.elements if e.protected).name == "[protected]"


def test_the_element_cap_is_reported_honestly(site):
    html = "<p>row</p>" * 450
    _, read = show(site, "long", html)
    reading = read()
    assert (len(reading.elements), reading.complete) == (300, False)
    _, read = show(site, "long-raised", html, max_elements=1000)
    reading = read()
    assert (len(reading.elements), reading.complete) == (450, True)


def test_accessible_names_and_their_source(site):
    html = ('<span id="a">Delivery</span> <span id="b">address</span>'
            '<input aria-labelledby="a b" aria-label="ignored" id="x">'
            '<button aria-label="  Close   dialog ">x</button>'
            '<label for="y">  Full\n   name </label><input id="y">'
            '<a href="#t">Read\n more</a><input name="fallback">'
            '<button aria-labelledby="missing">Save</button>')
    _, read = show(site, "names", html)
    found = {(e.name, e.extra["name_source"]) for e in read().elements if e.role in {"edit", "button", "link"}}
    assert found == {("Delivery address", "aria-labelledby"), ("Close dialog", "aria-label"),
                     ("Full name", "label"), ("Read more", "content"), ("fallback", "name-attribute"),
                     ("Save", "content")}
