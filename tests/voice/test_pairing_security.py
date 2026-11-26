import base64
import copy
import io

import pytest
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from fastapi.testclient import TestClient

from voice.api import create_app
from voice.config import Settings
from voice.events import Events
from voice.pairing import Pairing

ORIGIN = "http://127.0.0.1:3000"


def test_allowed_browser_can_read_denials_without_exposing_them_to_other_origins():
    app=create_app(Settings(),Events('fake',io.StringIO()),None,'x'*48)
    with TestClient(app,base_url='http://127.0.0.1:8767') as client:
        response=client.get('/v1/apps',headers={'Origin':ORIGIN})
        assert response.status_code==403 and response.headers['Access-Control-Allow-Origin']==ORIGIN
        assert response.headers['Cache-Control']=='no-store'
        response=client.post('/v1/voice/stop',headers={'Origin':ORIGIN,'Content-Type':'text/plain'},content='denied')
        assert response.status_code==415 and response.headers['Access-Control-Allow-Origin']==ORIGIN
        response=client.get('/v1/apps',headers={'Origin':'https://untrusted.example'})
        assert response.status_code==403 and 'Access-Control-Allow-Origin' not in response.headers


class MemoryStore:
    def __init__(self): self.data = {}
    def read(self): return copy.deepcopy(self.data)
    def write(self, data): self.data = copy.deepcopy(data)


def key():
    private = ec.generate_private_key(ec.SECP256R1())
    numbers = private.public_key().public_numbers()
    enc = lambda n: base64.urlsafe_b64encode(n.to_bytes(32, "big")).decode().rstrip("=")
    return private, {"kty": "EC", "crv": "P-256", "x": enc(numbers.x), "y": enc(numbers.y)}


def sign(private, proof):
    der = private.sign(proof.encode(), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return base64.b64encode(r.to_bytes(32, "big")+s.to_bytes(32, "big")).decode()


def paired():
    prompts = []
    store = MemoryStore()
    pairing = Pairing(store, lambda *args: prompts.append(args))
    private, jwk = key()
    request = pairing.begin(ORIGIN, jwk)
    assert pairing.poll(ORIGIN, request["request_id"]) == {"state": "pending"}
    prompts.pop()[2](True)
    grant = pairing.poll(ORIGIN, request["request_id"])["grant_id"]
    return pairing, store, private, grant


def login(pairing, private, grant):
    challenge = pairing.challenge(ORIGIN, grant)
    return pairing.authenticate(ORIGIN, grant, challenge["challenge_id"], sign(private, challenge["proof"]))["token"]


def test_native_consent_and_persistent_proof_survive_restart_without_prompt():
    pairing, store, private, grant = paired()
    token = login(pairing, private, grant)
    pairing.identity.renew()
    assert pairing.connected()
    restarted = Pairing(store, lambda *args: pytest.fail("must not pair again"))
    assert not restarted.connected()  # no armed state or active lease restored
    login(restarted, private, grant)
    restarted.identity.renew()
    assert restarted.connected()
    with pytest.raises(PermissionError): restarted.authorize(ORIGIN, token)


def test_wrong_browser_and_replayed_proof_are_rejected():
    pairing, _, private, grant = paired()
    challenge = pairing.challenge(ORIGIN, grant)
    signature = sign(private, challenge["proof"])
    pairing.authenticate(ORIGIN, grant, challenge["challenge_id"], signature)
    with pytest.raises(PermissionError):
        pairing.authenticate(ORIGIN, grant, challenge["challenge_id"], signature)
    other, _ = key()
    with pytest.raises(PermissionError): login(pairing, other, grant)
    with pytest.raises(PermissionError): pairing.challenge("https://untrusted.invalid", grant)


def test_revoke_invalidates_sessions_and_single_use_tickets_immediately():
    pairing, _, private, grant = paired()
    token = login(pairing, private, grant)
    ticket = pairing.ticket(ORIGIN, token)
    assert pairing.consume(ORIGIN, ticket) == token
    with pytest.raises(PermissionError): pairing.consume(ORIGIN, ticket)
    stale = pairing.ticket(ORIGIN, token)
    pairing.revoke(ORIGIN, token)
    with pytest.raises(PermissionError): pairing.authorize(ORIGIN, token)
    with pytest.raises(PermissionError): pairing.consume(ORIGIN, stale)
    assert not pairing.connected()


def test_declined_request_and_private_key_payload_cannot_create_grants():
    prompts = []
    pairing = Pairing(MemoryStore(), lambda *args: prompts.append(args))
    _, jwk = key()
    request = pairing.begin(ORIGIN, jwk)
    prompts.pop()[2](False)
    assert pairing.poll(ORIGIN, request["request_id"])["state"] == "denied"
    assert not pairing.grants
    with pytest.raises(ValueError): pairing.begin(ORIGIN, {**jwk, "d": "private"})


def test_connection_lease_expires_even_with_retained_pairing():
    pairing, _, private, grant = paired()
    login(pairing, private, grant)
    pairing.identity.renew()
    assert pairing.connected()
    pairing.identity.deadline = 0
    assert not pairing.connected()
    assert grant in pairing.grants


def test_principal_change_rejects_an_existing_browser_session():
    pairing, _, private, grant = paired()
    token = login(pairing, private, grant)
    pairing.identity.renew()
    pairing.identity.principal = lambda: "different-principal"
    assert not pairing.connected()
    with pytest.raises(PermissionError): pairing.authorize(ORIGIN, token)


def test_http_boundary_origin_host_auth_size_and_cors():
    pairing, _, private, grant = paired()
    class Session:
        async def close(self): pass
    app = create_app(Settings(), Events("fake", io.StringIO()), Session(), "x"*32, pairing)
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        assert client.get("/v1/health").status_code == 200
        assert client.get("/v1/apps", headers={"Origin": ORIGIN}).status_code == 403
        assert client.get("/v1/health", headers={"Host": "attacker.invalid"}).status_code == 403
        assert client.post("/v1/heartbeat", json={}).status_code == 403
        assert client.post("/v1/heartbeat", json={}, headers={"Origin": "https://attacker.invalid"}).status_code == 403
        assert client.post("/v1/heartbeat", content="x"*9000,
            headers={"Origin": ORIGIN, "Content-Type": "application/json"}).status_code == 413
        response = client.options("/v1/session", headers={"Origin": ORIGIN,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert response.headers["access-control-allow-origin"] == ORIGIN
        response = client.post("/v1/pairing", json={"public_key": []}, headers={"Origin": ORIGIN})
        assert response.status_code == 403
        response = client.post("/v1/challenge", json={"grant_id": "revoked"}, headers={"Origin": ORIGIN})
        assert response.status_code == 410
        assert response.headers["access-control-allow-origin"] == ORIGIN
        token = login(pairing, private, grant)
        response = client.post("/v1/heartbeat", json={}, headers={"Origin": ORIGIN, "Authorization": "Bearer "+token})
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == ORIGIN


def test_disconnect_revokes_all_browser_grants_on_this_computer():
    pairing, _, private, grant = paired()
    token = login(pairing, private, grant)
    second_private, second_jwk = key()
    request = pairing.begin(ORIGIN, second_jwk)
    pairing.approve(request["request_id"], True)
    second_grant = pairing.poll(ORIGIN, request["request_id"])["grant_id"]
    second_token = login(pairing, second_private, second_grant)
    class Session:
        async def close(self): pass
    app = create_app(Settings(), Events("fake", io.StringIO()), Session(), "x"*32, pairing)
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        response = client.post("/v1/disconnect", json={}, headers={"Origin": ORIGIN, "Authorization": "Bearer "+token})
        assert response.status_code == 200
    assert not pairing.grants
    with pytest.raises(PermissionError): pairing.authorize(ORIGIN, second_token)


def test_observer_requires_single_use_origin_bound_ticket():
    from starlette.websockets import WebSocketDisconnect
    pairing, _, private, grant = paired()
    token = login(pairing, private, grant)
    class Session:
        async def close(self): pass
    app = create_app(Settings(), Events("fake", io.StringIO()), Session(), "x"*32, pairing)
    ticket = pairing.ticket(ORIGIN, token)
    with TestClient(app, base_url="http://127.0.0.1:8767") as client:
        with client.websocket_connect("/v1/voice/events", headers={"Origin": ORIGIN, "Host": "127.0.0.1:8767"}) as socket:
            socket.send_json({"type": "auth", "ticket": ticket})
            assert socket.receive_json()["type"] == "snapshot"
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/voice/events", headers={"Origin": ORIGIN, "Host": "127.0.0.1:8767"}) as socket:
                socket.send_json({"type": "auth", "ticket": ticket})
                socket.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/voice/events", headers={"Origin": "https://attacker.invalid"}):
                pass


def test_windows_dpapi_profile_roundtrip(tmp_path):
    import os
    if os.name != "nt": pytest.skip("Windows DPAPI")
    from voice.protected_store import ProtectedStore
    path = tmp_path / "pairing.dat"
    store = ProtectedStore(path)
    store.write({"grants": {"sample": {"origin": ORIGIN}}})
    assert ORIGIN.encode() not in path.read_bytes()
    assert store.read()["grants"]["sample"]["origin"] == ORIGIN


@pytest.mark.parametrize("origin", ["*", "https://*.example.com", "http://example.com", "https://example.com/path"])
def test_origin_configuration_rejects_unsafe_entries(origin):
    with pytest.raises(ValueError): Settings(origins=(origin,))
