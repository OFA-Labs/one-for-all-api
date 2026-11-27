"""Live form filling: a real browser (throwaway Edge profile), the real reasoning model, simulated spoken replies.

    python scripts/e2e_form.py --env-file .env                      # the local 6-page replica
    python scripts/e2e_form.py --env-file .env --window "My form"    # a form already open in a browser

The user's own "Use without consent" documents are copied into a temporary data folder, so nothing in the real
one changes. Replies to OFA's questions are scripted below; on a real form your voice gives them.
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REAL_CORPUS = Path(os.getenv("LOCALAPPDATA", str(Path.home()))) / "OFA/corpus/open"
os.environ["OFA_DATA_DIR"] = tempfile.mkdtemp(prefix="ofa-form-")

from ofa.config import OfaConfig, load_env_file  # noqa: E402
from ofa.policy.approval import Heard  # noqa: E402

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
REPLIES = [(r"foreign language", "Nil"), (r"relocate", "no"), (r"should i tick", "yes"),
           (r"about to submit|go ahead", "yes, go ahead"), (r"save your", "no"), (r"say continue", "skip")]


class Recorder(http.server.SimpleHTTPRequestHandler):
    submitted: dict = {}

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        Recorder.submitted = json.loads(body or b"{}")
        self.send_response(204)
        self.end_headers()


def close_replica_windows() -> None:
    """Close only windows showing the replica form (they belong to the throwaway profile)."""
    from ofa.harness import win
    for w in win.list_windows():
        if w["process"] == "msedge.exe" and w["title"].startswith("OFA Test Research Form"):
            win.close_window(w["hwnd"])


def start_replica() -> tuple[subprocess.Popen, str]:
    handler = functools.partial(Recorder, directory=str(ROOT / "ofa" / "ui"))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 8795), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    close_replica_windows()
    profile = tempfile.mkdtemp(prefix="ofa-edge-")
    edge = subprocess.Popen([EDGE, f"--user-data-dir={profile}", "--no-first-run", "--new-window", "--window-size=1100,900",
                             "http://127.0.0.1:8795/mock-ms-form.html"])
    time.sleep(6)
    return edge, "OFA Test Research Form"


async def main(window: str | None):
    from ofa.graphs.form import form_graph  # noqa: F401  (import errors surface before the browser opens)
    from ofa.runtime import build_core
    data = Path(os.environ["OFA_DATA_DIR"])
    if REAL_CORPUS.exists():
        shutil.copytree(REAL_CORPUS, data / "corpus" / "open")
    edge = None
    if window is None:
        edge, window = start_replica()
    core = build_core(OfaConfig())
    spoken: list[str] = []
    replies: list[tuple[str, str]] = []

    async def speak(text):
        spoken.append(text)
        print(f"  [{time.monotonic() - started:5.1f}s] OFA: {text[:200]}", flush=True)
        return time.monotonic() - 1.0

    async def listen(timeout):
        await asyncio.sleep(0.05)
        question = spoken[-1] if spoken else ""
        for pattern, reply in REPLIES:
            if re.search(pattern, question, re.I):
                replies.append((question[:80], reply))
                print(f"           you: {reply}", flush=True)
                return Heard(reply, 0.95, "mic")
        print("           you: (silence)", flush=True)
        return None
    core.voice.attach(speak=speak, listen=listen)
    started = time.monotonic()
    try:
        title = re.escape(window)
        result = await core.runner.handle(f"hey OFA I am running out of time, fill the form in the window {title.replace(chr(92), '')} quickly")
        seconds = time.monotonic() - started
        print(f"\nstatus={result.status} seconds={seconds:.1f}\nspoken={result.spoken}")
        metrics = core.engine.metrics().summary()
        print(f"model calls={metrics['calls']} errors={metrics['errors']} model={core.engine.info().model}")
        if edge is not None:
            print("submitted:", json.dumps(Recorder.submitted, ensure_ascii=False, indent=1))
            if not Recorder.submitted:                       # show where it stopped
                from ofa.eyes.form import read_form
                page = read_form(core.harness, window)
                print("stopped on page", page.page, [(f.question[:30], f.value[:40], f.error[:40]) for f in page.fields])
    finally:
        await core.runner.aclose()
        if edge is not None:
            close_replica_windows()
            edge.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file")
    parser.add_argument("--window", help="title of a form already open in a browser")
    args = parser.parse_args()
    load_env_file(args.env_file)
    asyncio.run(main(args.window))
