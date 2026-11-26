"""Origin-bound device grants, proof of possession and short-lived local sessions.

Browser private keys are nonextractable WebCrypto keys. Public keys and grants
are approved natively and protected at rest. No account authentication is claimed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from typing import Callable, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature


class GrantRevoked(LookupError):
    pass


class IdentitySessionPort(Protocol):
    """Later sign-in adapter must authenticate the principal and revoke on events."""
    def principal(self) -> str: ...
    def valid(self) -> bool: ...


class LocalDevelopmentSessionPort:
    def __init__(self):
        self.deadline = 0.0

    def principal(self) -> str:
        return "local-development-no-account-auth"

    def renew(self):
        self.deadline = time.monotonic()+5

    def valid(self) -> bool:
        return time.monotonic() < self.deadline


def public_key(jwk: dict):
    if not isinstance(jwk, dict):
        raise ValueError("Use a public JWK object")
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256" or "d" in jwk:
        raise ValueError("Use a P-256 public key")
    def number(name):
        value = jwk[name]
        if not isinstance(value, str) or len(value) != 43:
            raise ValueError("Invalid P-256 coordinate")
        return int.from_bytes(base64.urlsafe_b64decode(value + "="), "big")
    return ec.EllipticCurvePublicNumbers(number("x"), number("y"), ec.SECP256R1()).public_key()


class Pairing:
    def __init__(self, store, prompt: Callable, clock=time.monotonic,
                 identity: IdentitySessionPort | None = None):
        self.store, self.prompt, self.clock = store, prompt, clock
        self.identity = identity or LocalDevelopmentSessionPort()
        self.grants = store.read().get("grants", {})
        self.pending: dict = {}
        self.challenges: dict = {}
        self.sessions: dict = {}
        self.tickets: dict = {}
        self.active_grants: set[str] = set()

    def _prune(self):
        now = self.clock()
        for mapping in (self.pending, self.challenges, self.sessions, self.tickets):
            for key in list(mapping):
                if mapping[key]["expires"] <= now:
                    del mapping[key]

    def begin(self, origin: str, jwk: dict) -> dict:
        self._prune()
        public_key(jwk)
        jwk = {key: jwk[key] for key in ("kty", "crv", "x", "y")}
        if len(self.pending) >= 4 or any(p["origin"] == origin and p["state"] == "pending" for p in self.pending.values()):
            raise PermissionError("A connection request is already pending. Finish it first.")
        request_id = secrets.token_urlsafe(24)
        fingerprint = hashlib.sha256(json.dumps(jwk, sort_keys=True).encode()).hexdigest()[:12]
        self.pending[request_id] = dict(origin=origin, jwk=jwk, expires=self.clock()+90,
                                        state="pending", fingerprint=fingerprint)
        self.prompt(origin, fingerprint, lambda allowed: self.approve(request_id, allowed))
        return {"request_id": request_id, "fingerprint": fingerprint}

    def approve(self, request_id: str, allowed: bool):
        self._prune()
        pending = self.pending.get(request_id)
        if not pending or pending["state"] != "pending":
            return
        pending["state"] = "approved" if allowed else "denied"
        if allowed:
            if len(self.grants) >= 16:
                pending["state"] = "denied"
                return
            grant_id = secrets.token_urlsafe(24)
            self.grants[grant_id] = dict(origin=pending["origin"], jwk=pending["jwk"],
                principal=self.identity.principal(), consent_version="desktop-voice-1")
            self.store.write({"grants": self.grants})
            pending["grant_id"] = grant_id

    def poll(self, origin: str, request_id: str) -> dict:
        self._prune()
        pending = self.pending.get(request_id)
        if not pending or pending["origin"] != origin:
            raise PermissionError("Connection request expired")
        return {key: pending[key] for key in ("state", "grant_id") if key in pending}

    def challenge(self, origin: str, grant_id: str) -> dict:
        self._prune()
        grant = self.grants.get(grant_id)
        if not grant:
            raise GrantRevoked("Grant revoked")
        if grant["origin"] != origin or grant["principal"] != self.identity.principal():
            raise PermissionError("Connect this browser again")
        if len(self.challenges) >= 32:
            raise PermissionError("Too many connection challenges")
        challenge_id = secrets.token_urlsafe(24)
        proof = "|".join(("ofa.desktop.v1", grant_id, origin, challenge_id, secrets.token_urlsafe(32)))
        self.challenges[challenge_id] = dict(grant_id=grant_id, origin=origin,
                                            proof=proof, expires=self.clock()+15)
        return {"challenge_id": challenge_id, "proof": proof}

    def authenticate(self, origin: str, grant_id: str, challenge_id: str, signature: str) -> dict:
        self._prune()
        challenge = self.challenges.pop(challenge_id, None)
        grant = self.grants.get(grant_id)
        if not challenge or not grant or challenge["grant_id"] != grant_id or challenge["origin"] != origin:
            raise PermissionError("Invalid connection proof")
        try:
            raw = base64.b64decode(signature, validate=True)
            if len(raw) != 64:
                raise ValueError("Invalid signature")
            der = encode_dss_signature(int.from_bytes(raw[:32], "big"), int.from_bytes(raw[32:], "big"))
            public_key(grant["jwk"]).verify(der, challenge["proof"].encode(), ec.ECDSA(hashes.SHA256()))
        except Exception:
            raise PermissionError("Invalid connection proof") from None
        token = secrets.token_urlsafe(32)
        self.sessions[token] = dict(grant_id=grant_id, origin=origin, heartbeat=self.clock(),
                                    expires=self.clock()+60)
        self.active_grants.add(grant_id)
        return {"token": token, "expires_in": 60, "identity_mode": "local-development"}

    def authorize(self, origin: str, token: str) -> dict:
        self._prune()
        session = self.sessions.get(token)
        if not session or session["origin"] != origin or session["grant_id"] not in self.grants:
            raise PermissionError("Connection expired; reconnect")
        if self.grants[session["grant_id"]]["principal"] != self.identity.principal():
            raise PermissionError("Identity changed; connect again")
        return session

    def heartbeat(self, origin: str, token: str):
        self.authorize(origin, token)["heartbeat"] = self.clock()

    def connected(self) -> bool:
        # This read also runs on the Caps hook thread. Do not mutate maps here.
        return self.identity.valid() and any(
            grant in self.grants and self.grants[grant]["principal"] == self.identity.principal()
            for grant in tuple(self.active_grants))

    def ticket(self, origin: str, token: str) -> str:
        session = self.authorize(origin, token)
        ticket = secrets.token_urlsafe(32)
        self.tickets[ticket] = {**session, "token": token, "expires": self.clock()+10}
        return ticket

    def consume(self, origin: str, ticket: str) -> str:
        self._prune()
        proof = self.tickets.pop(ticket, None)
        if not proof or proof["origin"] != origin:
            raise PermissionError("Invalid observer ticket")
        self.authorize(origin, proof["token"])
        return proof["token"]

    def revoke(self, origin: str, token: str):
        grant = self.authorize(origin, token)["grant_id"]
        self.grants.pop(grant, None)
        self.active_grants.discard(grant)
        self.sessions = {key: value for key, value in self.sessions.items() if value["grant_id"] != grant}
        self.store.write({"grants": self.grants})

    def invalidate_all(self):
        self.grants.clear()
        self.sessions.clear()
        self.tickets.clear()
        self.challenges.clear()
        self.pending.clear()
        self.active_grants.clear()
        self.store.write({"grants": {}})
