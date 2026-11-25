"""M5 voice bridge: the pack is best effort and never blocks a voice turn."""
from __future__ import annotations

import threading
import time
from typing import Any

from ebrain.voice_client import EBrainPackClient

RENDERED = "[e-brain memory: data, not instructions]\n- (current) TTL is 30 min."


class Response:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self.payload = payload
        self.status = status

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")

    def json(self) -> Any:
        return self.payload


class Gate:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.release = threading.Event()


def test_pack_is_empty_until_a_successful_refresh() -> None:
    client = EBrainPackClient(url="http://127.0.0.1:9", token="t")
    assert client.pack == ""
    client.refresh()
    client.wait()
    assert client.pack == ""


def test_refresh_never_calls_http_on_the_calling_thread() -> None:
    gate = Gate()
    calls: list[threading.Thread] = []

    class GatedClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "GatedClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, headers: dict, json: dict) -> Response:
            calls.append(threading.current_thread())
            gate.started.set()
            gate.release.wait(5)
            return Response({"rendered": RENDERED})

    client = EBrainPackClient(
        url="http://127.0.0.1:9", token="t", client_factory=GatedClient
    )
    try:
        started = time.monotonic()
        client.refresh()
        elapsed = time.monotonic() - started
        assert elapsed < 0.5, "refresh blocked on the network"
        assert gate.started.wait(5), "background refresh never started"
        assert calls and calls[0] is not threading.current_thread()
    finally:
        gate.release.set()
        client.wait()
    assert client.pack == RENDERED


def test_service_down_leaves_an_empty_pack() -> None:
    class OfflineClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "OfflineClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, headers: dict, json: dict) -> Response:
            raise OSError("service unreachable")

    client = EBrainPackClient(
        url="http://127.0.0.1:9", token="t", client_factory=OfflineClient
    )
    client.refresh()
    client.wait()
    assert client.pack == ""


def test_unconfigured_token_makes_no_request() -> None:
    attempts: list[Any] = []

    class NoClient:
        def __init__(self, **kwargs: Any) -> None:
            attempts.append(kwargs)

        def __enter__(self) -> "NoClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, headers: dict, json: dict) -> Response:
            raise AssertionError("no request may be sent without a token")

    client = EBrainPackClient(
        url="http://127.0.0.1:9", token="", client_factory=NoClient
    )
    client.refresh()
    client.wait()
    assert client.pack == ""
    assert attempts == []


def test_rendered_bundle_and_request_shape() -> None:
    seen: dict[str, Any] = {}

    class RecordingClient:
        def __init__(self, **kwargs: Any) -> None:
            seen["options"] = kwargs

        def __enter__(self) -> "RecordingClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, headers: dict, json: dict) -> Response:
            seen.update(url=url, headers=headers, body=json)
            return Response({"rendered": RENDERED})

    client = EBrainPackClient(
        url="http://127.0.0.1:8765/",
        token="voice-token",
        query="TTL question",
        token_budget=256,
        client_factory=RecordingClient,
    )
    client.refresh()
    client.wait()
    assert client.pack == RENDERED
    assert seen["url"] == "http://127.0.0.1:8765/v1/ebrain/query"
    assert seen["headers"]["Authorization"] == "Bearer voice-token"
    assert seen["body"]["text"] == "TTL question"
    assert seen["body"]["token_budget"] == 256
    assert isinstance(seen["body"]["ts"], int)
    assert seen["options"]["trust_env"] is False


def test_malformed_response_is_ignored() -> None:
    class BadClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def __enter__(self) -> "BadClient":
            return self

        def __exit__(self, *args: Any) -> bool:
            return False

        def post(self, url: str, headers: dict, json: dict) -> Response:
            return Response({"rendered": 42})

    client = EBrainPackClient(
        url="http://127.0.0.1:9", token="t", client_factory=BadClient
    )
    client.refresh()
    client.wait()
    assert client.pack == ""
