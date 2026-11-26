"""Default-browser launch receipt; explicitly weaker than page readback."""
from __future__ import annotations

import ipaddress
import socket
import webbrowser
from urllib.parse import urlsplit

from .contracts import Evidence, ExecutionError, Observation, Outcome
from voice.websites import validate_url


def public_url(raw):
    try:
        url = validate_url(raw)
        parsed = urlsplit(url)
        rows = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
        if not rows or any(not ipaddress.ip_address(row[4][0]).is_global for row in rows):
            raise ValueError()
        return url
    except (ValueError, OSError) as exc:
        raise ExecutionError("URL_DENIED", "Use a resolvable public HTTP(S) address.") from exc


class WebsiteHand:
    def __init__(self, config=None):
        self.config = config

    def capabilities(self):
        return {"operations": ["website.open"], "verification": "os_dispatch_only"}

    def observe(self, step):
        browser = None
        if step.target.app:
            from pathlib import Path
            browser = self.config.app(step.target.app)
            if browser.launch_kind != "exe" or Path(browser.executable).stem.lower() not in {"chrome","msedge","firefox"}:
                raise ExecutionError("BROWSER_NOT_SUPPORTED", "Select an installed Chrome, Edge or Firefox executable.")
        return Observation(surface="website", identity={"url": public_url(step.url or ""),"browser":browser.name if browser else "default"},
                           facts={"verification": "os_dispatch_only"})

    def execute(self, step, before, checkpoint):
        url = public_url(step.url or "")
        checkpoint()
        if step.target.app:
            import subprocess
            browser = self.config.app(step.target.app)
            # The only supplied argument is the validated HTTP(S) URL; no flags,
            # shell, profile changes or raw arguments from the browser/voice.
            process = subprocess.Popen([browser.executable, url], shell=False)
            good = process.poll() in (None,0)
        else:
            good = bool(webbrowser.open(url, new=2))
        after = before.model_copy(deep=True)
        after.facts["dispatched"] = good
        return Outcome(status="verified" if good else "unknown", observation=after,
                       evidence=[Evidence(tier="A", kind="os_url_dispatch", reading_hash=after.hash)])
