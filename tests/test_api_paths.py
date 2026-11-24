"""Encoded path-based chain histories remain accessible and tenant-scoped."""
from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient

from ebrain.api import create_app


def test_encoded_path_chain_history_is_scoped_to_user(tmp_path: Path) -> None:
    app = create_app({
        "data_dir": str(tmp_path),
        "tokens": {
            "path-a": {"user": "u-path-a", "agent": "claude", "human": False},
            "path-b": {"user": "u-path-b", "agent": "claude", "human": False},
        },
    })
    headers = {"Authorization": "Bearer path-a"}
    with TestClient(app) as client:
        for op_id, ts, value, code in (
            ("path-1", 1, 45, "VC-AUTH45"),
            ("path-2", 2, 30, "VC-AUTH30"),
        ):
            written = client.post("/v1/ebrain/write", headers=headers, json={
                "op_id": op_id,
                "ts": ts,
                "visibility": "shared",
                "kind": "spec",
                "text": f"The auth token TTL is {value} minutes ({code}).",
                "path": "docs/specs/auth.md",
            })
            assert written.status_code == 200
            assert written.json() == {"accepted": True, "reason": ""}

        chains = client.get("/v1/ebrain/chains", headers=headers).json()
        chain = chains["chains"][0]["chain"]
        assert chain == "p:docs/specs/auth.md"
        endpoint = "/v1/ebrain/chains/" + quote(chain, safe="")
        history = client.get(endpoint, headers=headers)
        assert history.status_code == 200
        assert history.json()["chain"] == chain
        assert [
            (version["op_id"], version["status"])
            for version in history.json()["versions"]
        ] == [("path-1", "superseded"), ("path-2", "current")]

        other_user = client.get(
            endpoint, headers={"Authorization": "Bearer path-b"}
        )
        assert other_user.status_code == 404
        assert other_user.json() == {"detail": "unknown chain"}
