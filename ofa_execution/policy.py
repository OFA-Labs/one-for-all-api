"""The single local policy gate and its process-scoped signed, one-use grants."""
from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

from .contracts import ExecutionError, Observation, Plan, Step, digest, uid


class Gate:
    def __init__(self, config):
        self.config = config
        self._key = secrets.token_bytes(32)
        self._spent: set[str] = set()
        self._lock = threading.RLock()

    def url(self, raw: str, plan: Plan) -> str:
        parsed = urlsplit(raw)
        if parsed.username or parsed.password or parsed.scheme not in {"https", "http"} or not parsed.hostname:
            raise ExecutionError("URL_DENIED", "Only permitted HTTP(S) origins are available.")
        origin = f"{parsed.scheme}://{parsed.netloc.lower()}"
        allowed = set(plan.allowed_origins) & set(self.config.allowed_origins + self.config.fixture_origins)
        if origin not in allowed:
            raise ExecutionError("ORIGIN_NOT_ALLOWED", "The origin is absent from the frozen plan or local permissions.")
        if origin not in self.config.fixture_origins:
            if parsed.scheme != "https":
                raise ExecutionError("URL_DENIED", "Public browser targets require HTTPS.")
            try:
                addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
                if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                    raise ExecutionError("PRIVATE_NETWORK_DENIED", "Private/local network targets are excluded.")
            except socket.gaierror as exc:
                raise ExecutionError("DNS_FAILED", "Target host could not be resolved.") from exc
        if any(word in parsed.hostname.lower() for word in
               ("bank", "paypal", "crypto", "1password", "bitwarden", "lastpass")):
            raise ExecutionError("POLICY_DENIED", "This sensitive category is excluded.")
        return origin

    def screen(self, plan: Plan):
        for step in plan.steps:
            if step.operation.startswith(("app.", "desktop.", "window.")):
                self.config.app(step.target.app or "")
            if step.operation == "browser.open":
                self.url(step.url or "", plan)
            if step.operation.startswith("file."):
                self.config.file(step.target.path or "", step.operation == "file.write")

    def check(self, step: Step, before: Observation) -> str:
        if not before.complete:
            raise ExecutionError("READING_INCOMPLETE", "The surface cannot be read completely; human assistance is required.")
        if before.facts.get("human_required"):
            return "handoff"
        if before.facts.get("protected"):
            raise ExecutionError("POLICY_DENIED", "Protected content is not accessible.")
        if step.operation.startswith("browser.") and step.operation not in {"browser.open", "browser.observe", "browser.screenshot", "browser.close"}:
            host = urlsplit(before.facts.get("url", "")).hostname or ""
            if host == "linkedin.com" or host.endswith(".linkedin.com"):
                return "handoff"
        if step.operation in {"browser.click", "desktop.click"}:
            candidates = [e for e in before.elements if
                          (e.ref == step.target.ref if step.target.ref else
                           (step.target.name is None or e.name.casefold() == step.target.name.casefold()) and
                           (step.target.role is None or e.role.casefold() == step.target.role.casefold()))]
            for element in candidates:
                name = element.name.strip().casefold()
                if name in {"pay", "purchase", "buy now", "checkout", "confirm payment"} or "captcha" in name:
                    return "handoff"
                surface = (before.identity.get("app", "") + " " + before.facts.get("url", "")).casefold()
                if "whatsapp" in surface and name in {"send", "send message"}:
                    return "handoff"
        mutations = {"desktop.click", "desktop.fill", "desktop.type", "desktop.scroll",
                     "browser.click", "browser.fill", "file.write"}
        # Unknown controls and autosave are never assumed harmless. Even filling
        # a field gets a card in the local milestone. No model can lower this.
        if step.operation in mutations:
            if step.expect is None:
                raise ExecutionError("ASSERTION_REQUIRED", "A mutation needs an explicit readback expectation.")
            return "approval"
        return "allow"

    def sign(self, task: str, step: Step, reading: Observation, epoch: int) -> str:
        body = {"jti": uid(), "task": task, "step": step.id, "action": digest(step.model_dump()),
                "reading": reading.hash, "epoch": epoch,
                "exp": time.monotonic() + self.config.approval_seconds}
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode() + "." + hmac.new(self._key, raw, hashlib.sha256).hexdigest()

    def consume(self, token: str, task: str, step: Step, reading: Observation, epoch: int):
        with self._lock:
            try:
                encoded, signature = token.split(".")
                raw = base64.urlsafe_b64decode(encoded)
                if not hmac.compare_digest(signature, hmac.new(self._key, raw, hashlib.sha256).hexdigest()):
                    raise ValueError()
                body = json.loads(raw)
            except (ValueError, TypeError, KeyError) as exc:
                raise ExecutionError("TOKEN_INVALID", "Approval signature is invalid.") from exc
            expected = {"task": task, "step": step.id, "action": digest(step.model_dump()),
                        "reading": reading.hash, "epoch": epoch}
            if any(body.get(k) != v for k, v in expected.items()):
                raise ExecutionError("READING_CHANGED", "The action, reading or control epoch changed.")
            if body["exp"] < time.monotonic():
                raise ExecutionError("TOKEN_EXPIRED", "Approval expired.")
            if body["jti"] in self._spent:
                raise ExecutionError("TOKEN_SPENT", "Approval was already consumed.")
            self._spent.add(body["jti"])
