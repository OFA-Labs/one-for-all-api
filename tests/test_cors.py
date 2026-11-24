"""The browser client may access the API from two local web origins."""
from pathlib import Path

from fastapi.testclient import TestClient

from ebrain.api import create_app


def test_loopback_preflight_and_authenticated_limits(tmp_path: Path) -> None:
    app = create_app({
        "data_dir": str(tmp_path),
        "tokens": {
            "cors-human": {"user": "u-cors", "agent": "human", "human": True},
        },
    })
    with TestClient(app) as client:
        for origin in ("http://127.0.0.1:3000", "http://127.0.0.1:3100"):
            for path, method in (
                ("/v1/ebrain/limits", "GET"),
                ("/v1/ebrain/query", "POST"),
                ("/v1/ebrain/me", "DELETE"),
            ):
                preflight = client.options(path, headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": method,
                    "Access-Control-Request-Headers": (
                        "authorization,content-type"
                    ),
                })
                assert preflight.status_code == 200
                headers = preflight.headers
                assert headers["access-control-allow-origin"] == origin
                assert method in headers["access-control-allow-methods"]
                allowed_headers = (
                    headers["access-control-allow-headers"].lower()
                )
                assert "authorization" in allowed_headers
                assert "content-type" in allowed_headers
                assert "access-control-allow-credentials" not in headers

            authenticated = client.get("/v1/ebrain/limits", headers={
                "Origin": origin,
                "Authorization": "Bearer cors-human",
            })
            assert authenticated.status_code == 200
            headers = authenticated.headers
            assert headers["access-control-allow-origin"] == origin
            assert "access-control-allow-credentials" not in headers

            unauthenticated = client.get(
                "/v1/ebrain/limits", headers={"Origin": origin}
            )
            assert unauthenticated.status_code == 401
            assert unauthenticated.json() == {
                "detail": "missing or unknown bearer token"
            }
            headers = unauthenticated.headers
            assert headers["access-control-allow-origin"] == origin


def test_unlisted_origins_cannot_pass_preflight(tmp_path: Path) -> None:
    app = create_app({"data_dir": str(tmp_path), "tokens": {}})
    with TestClient(app) as client:
        for origin in (
            "https://example.com",
            "http://localhost:3100",
            "http://127.0.0.1:3101",
            "http://127.0.0.1:3100.attacker.example",
        ):
            preflight = client.options("/v1/ebrain/limits", headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            })
            assert preflight.status_code == 400
            assert "access-control-allow-origin" not in preflight.headers
