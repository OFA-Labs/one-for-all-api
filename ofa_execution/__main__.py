"""python -m ofa_execution --test-pad; no provider accounts required."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import socket
import sys
import webbrowser

from .browser import BrowserHand
from .config import App, LocalConfig
from .engine import Engine
from .files import FileHand
from .hotkey import StopHotkey
from .planner import DeterministicPlanner
from .windows import DesktopHand, discover_apps
from .takeover import TakeoverMonitor


def main():
    parser = argparse.ArgumentParser(description="OFA local deterministic execution")
    parser.add_argument("--config", help="Path to nonsecret local permissions JSON")
    parser.add_argument("--test-pad", action="store_true", help="Consent to the disposable OFA native fixture only")
    parser.add_argument("--discover", action="store_true", help="List installed App Paths metadata; grant no permissions")
    parser.add_argument("--no-browser", action="store_true", help="Use OFA_LOCAL_TOKEN configured locally; do not open UI")
    parser.add_argument("--port", type=int, default=0, help="Loopback port, 0 selects a free port")
    args = parser.parse_args()
    if args.discover:
        print(json.dumps(discover_apps(), indent=2))
        return
    config = LocalConfig.load(args.config)
    if args.test_pad:
        config.apps.append(App(name="OFA Test Pad", executable=getattr(sys, "_base_executable", sys.executable),
                               arguments=["-m", "ofa_execution.testpad"],
                               window_title="OFA Execution Test Pad", writable=True, capture=True))
    token = os.environ.get("OFA_LOCAL_TOKEN") or secrets.token_urlsafe(48)
    if args.no_browser and not os.environ.get("OFA_LOCAL_TOKEN"):
        parser.error("Set OFA_LOCAL_TOKEN in the local process environment for --no-browser; never paste it into chat.")
    hands = {"desktop": DesktopHand(config), "browser": BrowserHand(config), "files": FileHand(config)}
    engine = Engine(config, hands, DeterministicPlanner(config))
    hotkey = StopHotkey(engine.emergency_stop).start()
    takeover = TakeoverMonitor(lambda: hands["desktop"].active_window, engine.user_takeover).start()
    engine.runtime_capabilities = {"stop_hotkey": hotkey.available, "native_takeover": takeover.available}
    listener = socket.socket()
    listener.bind(("127.0.0.1", args.port))
    listener.listen(128)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    print(f"OFA local control: {origin}; planner=deterministic; hotkey={'Alt+Shift+J' if hotkey.available else 'unavailable (use Stop/console)'}")
    print("State is volatile. Restart invalidates approvals; check actual effects before repeating any action.")
    if not args.no_browser:
        # Fragment is not sent to HTTP/access logs; no secret is printed.
        webbrowser.open(origin + "/#" + token)
    import uvicorn
    from .api import create_app
    try:
        server = uvicorn.Server(uvicorn.Config(create_app(engine, token), access_log=False, log_level="warning"))
        server.run(sockets=[listener])
    finally:
        hotkey.close()
        takeover.close()
        listener.close()


if __name__ == "__main__":
    main()
