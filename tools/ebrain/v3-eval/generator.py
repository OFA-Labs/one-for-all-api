"""Deterministic synthetic dataset generator (test-only, no product imports).

Two independent workload modes are supported:

``event_count``
    exactly ``size`` events over ``size // canary_chains_per_events`` chains,
    with create / revise / erase actions and revision history;

``distinct_fact_count``
    exactly ``size`` *unique qualified keys*, plus a deterministic subset of
    revisions of those same keys (revisions never mint a new key).

Qualified keys are built from an integer token (``T{index:08d}``) combined
with repo/branch/namespace/environment qualifiers selected by a SHA-256 of
``seed:index``. There is no finite catalogue to exhaust: the token alone
guarantees uniqueness for any requested ``size``. All generation is a pure
function of ``(seed, size, mode)`` and can be streamed without materialising
the dataset in memory.

The public event stream contains no oracle identifiers, ground-truth labels
or hidden codes; it only contains structured selectors and values.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
from dataclasses import dataclass
from typing import Any, Iterator

from . import manifest

REVISION_EVERY = 8  # fallback; frozen value is protocol.dataset.distinct_revision_every


@dataclass(frozen=True)
class QualifiedKey:
    repo: str
    branch: str
    namespace: str
    environment: str
    token: str

    def canonical(self) -> str:
        return (f"{self.repo}|{self.branch}|{self.namespace}|"
                f"{self.environment}|{self.token}")


def make_key(index: int, seed: int, protocol: dict[str, Any]) -> QualifiedKey:
    """Qualified key from seed+index; uniqueness comes from the token."""
    q = protocol["dataset"]["qualifiers"]
    digest = hashlib.sha256(f"{seed}:{index}".encode("utf-8")).digest()
    return QualifiedKey(
        repo=q["repos"][digest[0] % len(q["repos"])],
        branch=q["branches"][digest[1] % len(q["branches"])],
        namespace=q["namespaces"][digest[2] % len(q["namespaces"])],
        environment=q["environments"][digest[3] % len(q["environments"])],
        token=f"T{index:08d}",
    )


@dataclass(frozen=True)
class Event:
    seq: int
    op_id: str
    ts: int
    action: str           # create | revise | erase
    key: str
    scope: str
    source: str
    authority: str
    value: str | None
    revision: int
    supersedes: tuple[str, ...]
    history: tuple[dict[str, Any], ...]
    facets: dict[str, str]
    scenario: str

    def to_json(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "op_id": self.op_id,
            "ts": self.ts,
            "action": self.action,
            "key": self.key,
            "scope": self.scope,
            "source": self.source,
            "authority": self.authority,
            "value": self.value,
            "revision": self.revision,
            "supersedes": list(self.supersedes),
            "history": [dict(h) for h in self.history],
            "facets": dict(self.facets),
            "scenario": self.scenario,
        }


def _op_id(seed: int, seq: int) -> str:
    return "op-" + hashlib.sha256(f"{seed}:{seq}".encode()).hexdigest()[:16]


def _value(seed: int, seq: int) -> str:
    return "v" + hashlib.sha256(f"val:{seed}:{seq}".encode()).hexdigest()[:10]


def _facets(key: QualifiedKey, scope: str) -> dict[str, str]:
    return {
        "repo": key.repo,
        "branch": key.branch,
        "namespace": key.namespace,
        "environment": key.environment,
        "scope": scope,
    }


def _scenario(rng: random.Random, protocol: dict[str, Any]) -> str:
    mix = protocol["dataset"]["scenario_mix"]
    return rng.choices(list(mix), weights=list(mix.values()), k=1)[0]


def _event_count_stream(seed: int, size: int, protocol: dict[str, Any]
                        ) -> Iterator[Event]:
    chains = max(1, size // protocol["dataset"]["canary_chains_per_events"])
    max_hist = int(protocol["dataset"]["max_revisions_per_key"])
    rng = random.Random(seed)
    heads: dict[int, tuple[Event, int]] = {}  # chain -> (last event, revision)
    for seq in range(1, size + 1):
        chain = (seq - 1) % chains
        scenario = _scenario(rng, protocol)
        base_ts = 100 + seq
        if scenario == "late":
            ts = max(100, base_ts - 7)
        elif scenario == "future":
            ts = 100000 + seq
        elif scenario == "conflict":
            ts = base_ts - (seq % 2)
        else:
            ts = base_ts
        scope = f"s{chain % 4}"
        qkey = make_key(chain, seed, protocol)
        prev = heads.get(chain)
        history: tuple[dict[str, Any], ...] = ()
        if prev is None:
            action, revision, supersedes = "create", 1, ()
        elif scenario == "erased":
            action, revision = "erase", prev[1] + 1
            supersedes = (prev[0].op_id,)
        else:
            action, revision = "revise", prev[1] + 1
            supersedes = (prev[0].op_id,)
            hist = list(prev[0].history)
            hist.append({"op_id": prev[0].op_id, "revision": prev[0].revision,
                         "ts": prev[0].ts, "value": prev[0].value,
                         "source": prev[0].source})
            history = tuple(hist[-max_hist:])
        value = None if action == "erase" else _value(seed, seq)
        authority = "human" if scenario in ("sequential", "erased") else "verified"
        source = f"src-{chain % 7:02d}"
        ev = Event(
            seq=seq, op_id=_op_id(seed, seq), ts=ts, action=action,
            key=qkey.canonical(), scope=scope, source=source,
            authority=authority, value=value, revision=revision,
            supersedes=supersedes, history=history,
            facets=_facets(qkey, scope), scenario=scenario,
        )
        if action != "erase":
            heads[chain] = (ev, revision)
        else:
            heads.pop(chain, None)
        yield ev


def _distinct_stream(seed: int, size: int, protocol: dict[str, Any]
                     ) -> Iterator[Event]:
    max_hist = int(protocol["dataset"]["max_revisions_per_key"])
    revision_every = int(protocol["dataset"]["distinct_revision_every"])
    seq = 0
    for index in range(size):
        seq += 1
        qkey = make_key(index, seed, protocol)
        scope = f"s{index % 4}"
        scenario = ("scoped" if index % 3 == 0 else
                    "conflict" if index % 5 == 0 else "sequential")
        first = Event(
            seq=seq, op_id=_op_id(seed, seq), ts=100 + index, action="create",
            key=qkey.canonical(), scope=scope, source=f"src-{index % 7:02d}",
            authority="human" if index % 2 == 0 else "verified",
            value=_value(seed, seq), revision=1, supersedes=(),
            history=(), facets=_facets(qkey, scope), scenario=scenario,
        )
        yield first
        if index % revision_every == 0:
            seq += 1
            hist = ({"op_id": first.op_id, "revision": 1, "ts": first.ts,
                     "value": first.value, "source": first.source},)[-max_hist:]
            yield Event(
                seq=seq, op_id=_op_id(seed, seq), ts=101 + index,
                action="revise", key=qkey.canonical(), scope=scope,
                source=f"src-{(index + 1) % 7:02d}", authority="verified",
                value=_value(seed, seq), revision=2,
                supersedes=(first.op_id,), history=hist,
                facets=_facets(qkey, scope), scenario="sequential",
            )


def iter_events(seed: int, size: int, mode: str,
                protocol: dict[str, Any] | None = None) -> Iterator[Event]:
    """Stream events; ``mode`` must be one of the frozen protocol modes."""
    proto = protocol or manifest.load_protocol()
    if mode not in proto["dataset"]["modes"]:
        raise ValueError(f"unknown mode {mode!r}; expected "
                         f"{proto['dataset']['modes']}")
    if size < 0:
        raise ValueError("size must be >= 0")
    if mode == "event_count":
        yield from _event_count_stream(seed, size, proto)
    else:
        yield from _distinct_stream(seed, size, proto)


def generate(seed: int, size: int, mode: str,
             protocol: dict[str, Any] | None = None) -> list[Event]:
    """Materialise a dataset (use :func:`iter_events` for large workloads)."""
    return list(iter_events(seed, size, mode, protocol))


class DatasetStats:
    """Accumulator for streamed counts and the stable dataset hash."""

    def __init__(self) -> None:
        self.h = hashlib.sha256()
        self.event_count = 0
        self.keys: set[str] = set()
        self.revision_count = 0
        self.max_revision = 0
        self.scenario_counts: dict[str, int] = {}

    def add(self, ev: Event) -> None:
        self.h.update(manifest.canonical_json(ev.to_json()) + b"\n")
        self.event_count += 1
        self.keys.add(ev.key)
        self.revision_count += int(ev.action == "revise")
        self.max_revision = max(self.max_revision, ev.revision)
        key = ev.scenario
        self.scenario_counts[key] = self.scenario_counts.get(key, 0) + 1

    def finish(self) -> dict[str, Any]:
        return {
            "event_count": self.event_count,
            "distinct_fact_count": len(self.keys),
            "revision_count": self.revision_count,
            "max_revision": self.max_revision,
            "scenario_counts": dict(sorted(self.scenario_counts.items())),
            "stream_sha256": self.h.hexdigest(),
        }


def stream_stats(seed: int, size: int, mode: str,
                 protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Hash and count a dataset without retaining any event objects."""
    stats = DatasetStats()
    for ev in iter_events(seed, size, mode, protocol):
        stats.add(ev)
    return stats.finish()


def write_dataset(out_dir: str, seed: int, size: int, mode: str,
                  protocol: dict[str, Any] | None = None) -> dict[str, Any]:
    """Write ``events.jsonl`` + a sealed ``dataset_manifest.json``."""
    proto = protocol or manifest.load_protocol()
    os.makedirs(out_dir, exist_ok=True)
    stats = DatasetStats()
    events_path = os.path.join(out_dir, "events.jsonl")
    with open(events_path, "w", encoding="utf-8") as fh:
        for ev in iter_events(seed, size, mode, proto):
            fh.write(json.dumps(ev.to_json(), **manifest.CANON) + "\n")
            stats.add(ev)
    body = {
        "dataset_schema_version": 1,
        "protocol_id": proto["protocol_id"],
        "protocol_version": proto["protocol_version"],
        "protocol_hash": manifest.protocol_hash(),
        "seed": seed,
        "size": size,
        "mode": mode,
        "counts": stats.finish(),
        "events_sha256": manifest.sha256_file(events_path),
    }
    sealed = manifest.seal_manifest(body)
    with open(os.path.join(out_dir, "dataset_manifest.json"), "w",
              encoding="utf-8") as fh:
        json.dump(sealed, fh, **manifest.CANON)
    return sealed


__all__ = [
    "REVISION_EVERY", "QualifiedKey", "Event", "make_key", "iter_events",
    "generate", "DatasetStats", "stream_stats", "write_dataset",
]
