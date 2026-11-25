"""Offline calibration of pinned local embedding/reranker candidates.

Development data only (no sealed or pilot labels). Measures exact-vs-semantic
recall@5, reranker delta and CPU latency. Activation stays OFF unless gates pass.
"""
from __future__ import annotations

import datetime
import json
import random
import statistics
import time
from pathlib import Path

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer

API = Path(__file__).resolve().parents[3]
OUT = API / "docs/ebrain/implementation-plan/evidence/calibration"
EMBED = "intfloat/multilingual-e5-small"
RERANK = "cross-encoder/ms-marco-MiniLM-L6-v2"
N = 300
QUERIES = 120


def main() -> int:
    rng = random.Random(20261125)
    OUT.mkdir(parents=True, exist_ok=True)
    docs: list[str] = []
    expected: list[int] = []
    for i in range(N):
        repo = ("one-for-all-api", "one-for-all-web")[i % 2]
        env = ("dev", "stage", "prod")[i % 3]
        docs.append(f"Decision {i}: {repo} {env} branch main uses storage backend value-{i}")
        expected.append(i)
    queries: list[tuple[str, int]] = []
    for i in rng.sample(range(N), QUERIES):
        repo = "one-for-all-api" if i % 2 == 0 else "one-for-all-web"
        env = ("dev", "stage", "prod")[i % 3]
        queries.append((f"what is the storage backend decision for {repo} {env}?", i))

    encoder = SentenceTransformer(EMBED)
    reranker = CrossEncoder(RERANK)
    doc_start = time.perf_counter()
    doc_emb = encoder.encode(["passage: " + d for d in docs], batch_size=32,
                             normalize_embeddings=True, show_progress_bar=False)
    embed_doc_ms = (time.perf_counter() - doc_start) * 1000

    recalls_exact: list[float] = []
    recalls_rerank: list[float] = []
    latencies: list[float] = []
    for text, truth in queries:
        start = time.perf_counter()
        q = encoder.encode("query: " + text, normalize_embeddings=True,
                           show_progress_bar=False)
        scores = np.asarray(doc_emb) @ np.asarray(q)
        top = np.argsort(-scores)[:5]
        latencies.append((time.perf_counter() - start) * 1000)
        recalls_exact.append(1.0 if truth in top.tolist() else 0.0)
        pairs = [(text, docs[int(idx)]) for idx in top]
        reranked = reranker.predict(pairs, batch_size=5)
        best = top[int(np.argmax(reranked))]
        recalls_rerank.append(1.0 if int(best) == truth else 0.0)

    report = {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "models": {"embedding": EMBED, "reranker": RERANK},
        "development_facts": N,
        "queries": QUERIES,
        "embedding_dimensions": int(np.asarray(doc_emb).shape[1]),
        "semantic_recall_at_5": round(statistics.mean(recalls_exact), 4),
        "rerank_recall_at_1": round(statistics.mean(recalls_rerank), 4),
        "encode_all_docs_ms": round(embed_doc_ms, 2),
        "query_latency_ms_p50": round(statistics.median(latencies), 3),
        "query_latency_ms_p95": round(sorted(latencies)[int(len(latencies) * 0.95)], 3),
        "gates": {
            "recall_at_5_min": 0.99,
            "recall_at_5_pass": statistics.mean(recalls_exact) >= 0.99,
            "p95_ms_max": 200,
            "latency_pass": sorted(latencies)[int(len(latencies) * 0.95)] < 200,
        },
        "activation": "NOT_ACTIVATED",
        "note": "Development calibration only. Sealed/pilot strata not used; no model is on the authoritative path.",
    }
    path = OUT / "calibration.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
