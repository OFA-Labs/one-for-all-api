"""Pin approved local model artifacts with SHA-256 and an offline smoke test.

Downloads vetted public models into the local cache only; no repository or pilot
content is sent anywhere. No artifact becomes active until hashes are recorded.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path

API = Path(__file__).resolve().parents[3]
OUT = API / "docs/ebrain/implementation-plan/evidence/models"
MODELS = {
    "embedding_primary": "intfloat/multilingual-e5-small",
    "embedding_comparison": "BAAI/bge-small-en-v1.5",
    "reranker": "cross-encoder/ms-marco-MiniLM-L6-v2",
}


def file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    from sentence_transformers import CrossEncoder, SentenceTransformer

    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "runtime": "CPU / sentence-transformers",
        "egress_policy": "download only; no data sent; inference offline after pinning",
        "models": {},
    }
    for role, model_id in MODELS.items():
        model = (CrossEncoder(model_id) if role == "reranker"
                 else SentenceTransformer(model_id))
        root = Path(model.model_card_data.base_model) if hasattr(model, "model_card_data") else None
        # Resolve cached files from the model's own modules instead of guessing a path.
        files: set[Path] = set()
        modules_attr = getattr(model, "modules", None)
        modules = modules_attr() if callable(modules_attr) else (modules_attr or [model])
        for module in modules:
            first = getattr(module, "first_module", lambda: module)()
            path = getattr(first, "_model_config", None)
            if path is not None and getattr(path, "name_or_path", None):
                candidate = Path(path.name_or_path)
                if candidate.is_dir():
                    files.update(p for p in candidate.rglob("*") if p.is_file())
        if not files:
            # Fall back to the sentence-transformers cache directory for this id.
            cache = Path.home() / ".cache/huggingface/hub"
            safe = "models--" + model_id.replace("/", "--")
            root = cache / safe
            if root.is_dir():
                files.update(p for p in root.rglob("*")
                             if p.is_file() and "snapshots" in p.parts)
        hashes = {p.name: file_digest(p) for p in sorted(files)}
        aggregate = hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode("utf-8")
        ).hexdigest()
        sample = (model.encode(["query: auth decision"])
                  if role != "reranker" else model.predict([("query", "auth decision")]))
        manifest["models"][role] = {
            "model_id": model_id,
            "file_count": len(files),
            "artifact_sha256": aggregate,
            "file_hashes": hashes,
            "smoke_dimensions": int(len(sample[0])) if role != "reranker" else 1,
            "status": "PINNED_NOT_CALIBRATED",
        }
        print(role, "pinned", aggregate[:12], "files", len(files))
    (OUT / "model-manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
