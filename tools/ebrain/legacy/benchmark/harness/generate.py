"""Seeded synthetic project generator (INTERFACE.md section 3).

``generate(size, seed)`` returns a :class:`harness.scenarios.Dataset`: the
public write stream, the queries, traces and probes, plus the sealed truth.
This module holds the low-level world: the seeded RNG, opaque ids, value
codes, the ONE FOR ALL subject catalogue, text templates and filler writes.
The scenario plan lives in :mod:`harness.scenarios`.

CLI::

    python -m harness.generate --size 1000 --seed 101 --out data/ds-1000-101

writes ``writes.jsonl`` (public stream), ``queries.jsonl`` and
``sealed_truth.json`` (harness-only) and prints the stream hash.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from dataclasses import asdict, dataclass

from .api import Write

ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
AGENTS = ("claude", "codex", "voice")
PROJECTS = ("one-for-all", "jarvis")
KIND_MIX = {"spec": 0.15, "code": 0.20, "skill": 0.05, "log": 0.20,
            "claim": 0.20, "decision": 0.05, "dependency": 0.05,
            "task": 0.05, "summary": 0.05}
FILE_KINDS = ("spec", "code", "skill", "log")
REASONS = ("the security review", "the load test", "a customer escalation",
           "the cost review", "Tuesday's incident", "a vendor pricing change",
           "QA feedback", "the latency budget", "legal's request",
           "the on-call retro", "beta user feedback", "the SOC2 audit")
PEOPLE = ("Jai", "the product owner", "the infra lead", "security",
          "the voice team", "ops")


def kind_mix(size: int) -> dict[str, float]:
    """Kind shares; S7 (size >= 10000) raises logs to 40%."""
    if size < 10000:
        return dict(KIND_MIX)
    rest = {k: v for k, v in KIND_MIX.items() if k != "log"}
    scale = 0.60 / sum(rest.values())
    mix = {k: v * scale for k, v in rest.items()}
    mix["log"] = 0.40
    return mix


# --------------------------------------------------------------- catalogue
@dataclass(frozen=True)
class Fact:
    key: str
    aliases: tuple[str, ...]
    values: tuple[str, ...]
    spec: str          # spec file stem under docs/specs/
    module: str        # src/<module>/config.py
    const: str
    skill: str | None
    group: str         # ambiguity term shared with near-miss facts


def _f(key: str, aliases: str, values: str, spec: str, module: str,
       const: str, skill: str | None, group: str) -> Fact:
    return Fact(key, tuple(aliases.split("|")), tuple(values.split("|")),
                spec, module, const, skill, group)


FACTS: tuple[Fact, ...] = (
    _f("auth_ttl", "auth token TTL|auth-token TTL|TTL of the auth token|"
       "token ttl for auth|access token lifetime",
       "15 minutes|30 minutes|45 minutes|60 minutes|90 minutes|2 hours",
       "auth", "auth", "AUTH_TOKEN_TTL", None, "TTL"),
    _f("refresh_ttl", "refresh token TTL|refresh-token TTL|TTL of the "
       "refresh token|refresh token lifetime",
       "1 day|3 days|7 days|14 days|30 days|60 days",
       "auth-refresh", "auth", "REFRESH_TOKEN_TTL", None, "TTL"),
    _f("approval_ttl", "approval token validity|approval-token TTL|"
       "how long approval tokens stay valid|approval link expiry",
       "5 minutes|10 minutes|15 minutes|30 minutes|1 hour",
       "approvals", "approvals", "APPROVAL_TOKEN_TTL", None, "TTL"),
    _f("gradium_sessions", "Gradium session limit|Gradium concurrent "
       "session cap|max Gradium sessions|Gradium sessions ceiling",
       "2|4|5|8|10|16|20", "gradium", "voice", "GRADIUM_MAX_SESSIONS",
       None, "session limit"),
    _f("supabase_sessions", "Supabase pooler session limit|Supabase "
       "session limit|max pooled Supabase sessions",
       "15|20|30|60|90|120", "supabase", "api", "SUPABASE_POOL_SIZE",
       None, "session limit"),
    _f("stt_provider", "STT provider|speech-to-text provider|"
       "transcription vendor|STT backend",
       "Deepgram|AssemblyAI|Whisper (local)|Gladia|Speechmatics",
       "voice-pipeline", "voice", "STT_PROVIDER", None, "provider"),
    _f("tts_provider", "TTS provider|text-to-speech vendor|voice "
       "synthesis provider|TTS backend",
       "ElevenLabs|Cartesia|Gradium|Piper (local)|PlayHT",
       "voice-output", "voice", "TTS_PROVIDER", None, "provider"),
    _f("worker_budget", "worker action budget|per-run action budget for "
       "workers|max actions per worker run|worker step budget",
       "20|30|40|50|75|100|150", "workers", "workers",
       "WORKER_ACTION_BUDGET", "web-research", "budget"),
    _f("context_budget", "context token budget|prompt token budget|max "
       "context tokens|context window budget",
       "4000|8000|12000|16000|32000", "memory", "memory",
       "CONTEXT_TOKEN_BUDGET", None, "budget"),
    _f("blocklist", "default blocklist|default domain blocklist|"
       "blocked-domains default list|default site blocklist",
       "linkedin.com, indeed.com|facebook.com, x.com|tiktok.com|"
       "reddit.com, quora.com|none|glassdoor.com, monster.com",
       "browser-worker", "workers", "DEFAULT_BLOCKLIST", "job-apply",
       "blocklist"),
    _f("supabase_plan", "Supabase plan|Supabase tier|database plan on "
       "Supabase|Supabase subscription",
       "Free|Pro|Team|Enterprise", "supabase-billing", "api",
       "SUPABASE_PLAN", None, "plan"),
    _f("vercel_plan", "Vercel plan|Vercel tier|hosting plan on Vercel",
       "Hobby|Pro|Enterprise", "hosting", "web", "VERCEL_PLAN", None,
       "plan"),
    _f("apply_cap", "job-apply daily cap|max applications per day|daily "
       "application limit for job-apply|job-apply daily limit",
       "5|10|15|20|25|40", "job-apply", "jobs", "DAILY_APPLY_CAP",
       "job-apply", "limit"),
    _f("sample_rate", "voice pipeline sample rate|audio sample rate|mic "
       "sample rate|capture sample rate",
       "8000 Hz|16000 Hz|22050 Hz|24000 Hz|48000 Hz", "voice-pipeline",
       "voice", "SAMPLE_RATE_HZ", None, "rate"),
    _f("vad_timeout", "VAD silence timeout|end-of-speech silence "
       "threshold|silence cutoff for VAD|VAD hangover",
       "300 ms|500 ms|700 ms|800 ms|1000 ms|1200 ms", "voice-pipeline",
       "voice", "VAD_SILENCE_MS", None, "timeout"),
    _f("fallback_model", "LLM fallback model|fallback model|backup LLM|"
       "model used when the primary fails",
       "small-fast-v2|mid-tier-2025|local-8b-instruct|reasoning-lite",
       "llm-routing", "common", "FALLBACK_MODEL", None, "model"),
    _f("embed_model", "embedding model|vector embedding model|model used "
       "for embeddings", "embed-small-3|embed-large-3|bge-m3|e5-base",
       "memory", "memory", "EMBEDDING_MODEL", None, "model"),
    _f("webhook_retries", "webhook retry limit|max webhook retries|"
       "webhook redelivery attempts", "3|5|8|10|12",
       "webhooks", "api", "WEBHOOK_MAX_RETRIES", None, "limit"),
    _f("user_rate", "API rate limit per user|per-user request limit|"
       "user request rate cap", "30 req/min|60 req/min|120 req/min|"
       "300 req/min|600 req/min", "api-gateway", "api",
       "USER_RATE_LIMIT", None, "rate limit"),
    _f("gradium_rate", "Gradium API rate limit|Gradium request quota|"
       "requests per minute to Gradium", "100 rpm|200 rpm|500 rpm|"
       "1000 rpm|2000 rpm", "gradium", "voice", "GRADIUM_RPM", None,
       "rate limit"),
    _f("log_retention", "log retention period|how long we keep logs|log "
       "retention|retention for run logs", "7 days|14 days|30 days|"
       "90 days|180 days", "observability", "common", "LOG_RETENTION",
       None, "retention"),
    _f("memory_retention", "memory retention window|how long memories "
       "are kept|retention for agent memories", "30 days|90 days|"
       "180 days|1 year|forever", "memory", "memory", "MEMORY_RETENTION",
       None, "retention"),
    _f("deploy_region", "deploy region|hosting region|primary region|"
       "production region", "eu-west-1|us-east-1|ap-south-1|eu-central-1|"
       "us-west-2", "deploy", "common", "DEPLOY_REGION", None, "region"),
    _f("node_version", "Node version|Node.js runtime version|node "
       "runtime", "18.19|20.11|20.17|22.3|22.11", "web-build", "web",
       "NODE_VERSION", None, "version"),
    _f("python_version", "worker Python version|Python runtime for "
       "workers|python version on workers", "3.10|3.11|3.12|3.13",
       "workers", "workers", "PYTHON_VERSION", None, "version"),
    _f("upload_size", "max upload size|upload size limit|largest "
       "allowed upload", "5 MB|10 MB|25 MB|50 MB|100 MB", "uploads",
       "api", "MAX_UPLOAD_MB", None, "limit"),
    _f("idle_timeout", "session idle timeout|idle logout timer|"
       "inactivity timeout", "10 minutes|15 minutes|30 minutes|"
       "1 hour|4 hours", "auth", "auth", "IDLE_TIMEOUT", None, "timeout"),
    _f("bargein", "barge-in threshold|interrupt sensitivity|barge-in "
       "energy threshold", "-30 dB|-35 dB|-40 dB|-45 dB|-50 dB",
       "voice-pipeline", "voice", "BARGE_IN_DB", None, "threshold"),
    _f("wake_word", "wake word|hotword|activation phrase",
       "Jarvis|Hey Chitti|Computer|OK Friday|Hey Ofa", "voice-ux",
       "voice", "WAKE_WORD", None, "word"),
    _f("vector_store", "vector store|vector database|ANN index backend",
       "pgvector|Qdrant|LanceDB|sqlite-vss|Chroma", "memory", "memory",
       "VECTOR_BACKEND", None, "store"),
    _f("ci_timeout", "CI test timeout|test job timeout in CI|CI timeout",
       "10 minutes|15 minutes|20 minutes|30 minutes|45 minutes",
       "ci", "common", "CI_TIMEOUT", "code-review", "timeout"),
    _f("quorum", "approval quorum|number of approvers required|approver "
       "count", "1|2|3|4", "approvals", "approvals", "APPROVAL_QUORUM",
       None, "threshold"),
    _f("browser_workers", "browser worker concurrency|parallel browser "
       "workers|max concurrent browser workers", "1|2|3|4|6|8",
       "browser-worker", "workers", "BROWSER_CONCURRENCY", "form-filler",
       "limit"),
    _f("digest_time", "daily digest time|digest cron schedule|time the "
       "morning digest goes out", "06:00 UTC|07:30 UTC|08:00 UTC|"
       "09:15 UTC|05:45 UTC", "notifications", "jobs", "DIGEST_CRON",
       "standup-notes", "schedule"),
    _f("otp_length", "OTP length|one-time code length|login code digits",
       "4|6|8", "auth", "auth", "OTP_DIGITS", None, "length"),
    _f("support_sender", "support sender address|reply-to for support "
       "mail|support email sender", "support@ofa.dev|help@ofa.dev|"
       "noreply@ofa.dev|team@ofa.dev", "notifications", "common",
       "SUPPORT_SENDER", "inbox-triage", "address"),
)

SCOPES: tuple[tuple[str, str], ...] = (
    ("", ""), ("for the web app", "web"), ("in staging", "staging"),
    ("for the voice worker", "voice-worker"), ("on mobile", "mobile"),
    ("for the API gateway", "gateway"),
    ("for enterprise tenants", "enterprise"),
    ("in the EU deployment", "eu"), ("for the beta cohort", "beta"),
)


@dataclass(frozen=True)
class Subject:
    """A fact in a scope: one chain subject."""

    fact: Fact
    scope: str
    slug: str

    def name(self, rng: random.Random) -> str:
        alias = rng.choice(self.fact.aliases)
        return f"{alias} {self.scope}".strip()

    @property
    def key(self) -> tuple[str, str]:
        return (self.fact.key, self.slug)


def all_subjects() -> list[Subject]:
    return [Subject(f, s, slug) for f in FACTS for s, slug in SCOPES]


# ------------------------------------------------------------------ world
class World:
    """Seeded source of ids, codes, values and texts."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self._ops: set[str] = set()
        self._codes: set[str] = set()
        self._paths: dict[str, set[str]] = {p: set() for p in PROJECTS}

    def op_id(self) -> str:
        while True:
            oid = "op-%012x" % self.rng.getrandbits(48)
            if oid not in self._ops:
                self._ops.add(oid)
                return oid

    def code(self) -> str:
        while True:
            c = "VC-" + "".join(self.rng.choice(ALNUM) for _ in range(6))
            if c not in self._codes:
                self._codes.add(c)
                return c

    def hexid(self, prefix: str) -> str:
        return f"{prefix}-%010x" % self.rng.getrandbits(40)

    def value(self, subj: Subject, avoid: str | None) -> str:
        opts = [v for v in subj.fact.values if v != avoid]
        return self.rng.choice(opts)

    def claim_path(self, project: str, kind: str, subj: Subject) -> str:
        """A unique, realistic path for a file-artifact chain."""
        f, slug = subj.fact, subj.slug
        sfx = f"-{slug}" if slug else ""
        if kind == "spec":
            cands = [f"docs/specs/{f.spec}{sfx}.md",
                     f"docs/design/{f.spec}{sfx}.md",
                     f"docs/rfcs/{f.spec}-{f.key.replace('_', '-')}{sfx}.md"]
        elif kind == "code":
            mod = slug.replace("-", "_")
            cands = [f"src/{f.module}/{f.key}{'_' + mod if mod else ''}.py",
                     f"src/{f.module}/settings/{f.key}{'_' + mod if mod else ''}.py"]
        else:
            name = f.skill or "ops-runbook"
            cands = [f"skills/{name}/SKILL.md" if not slug else
                     f"skills/{name}-{slug}/SKILL.md",
                     f"skills/{name}/{f.key}{sfx}.md"]
        used = self._paths[project]
        for c in cands:
            if c not in used:
                used.add(c)
                return c
        n = 2
        while True:
            stem, ext = os.path.splitext(cands[0])
            c = f"{stem}-{n}{ext}"
            if c not in used:
                used.add(c)
                return c
            n += 1

    def reserve_path(self, project: str, path: str) -> bool:
        if path in self._paths[project]:
            return False
        self._paths[project].add(path)
        return True


# ------------------------------------------------------------- fact texts
def fact_text(rng: random.Random, subj: Subject, kind: str, value: str,
              code: str, path: str | None) -> str:
    """Text of a fact-bearing write; always contains ``code`` verbatim."""
    name = subj.name(rng)
    reason = rng.choice(REASONS)
    who = rng.choice(PEOPLE)
    if kind == "spec":
        title = subj.fact.spec.replace("-", " ").title()
        extra = rng.choice((
            "Owners: platform team.", "Status: approved.",
            "See the runbook for rollout steps.",
            "Open question: monitoring thresholds."))
        return (f"# {title} spec\n\n## Settings\n- {name}: {value} ({code})\n"
                f"- changed after {reason}\n\n{extra}")
    if kind == "code":
        const = subj.fact.const
        return (f"# {path}\n\"\"\"Configuration for {subj.fact.module}.\"\"\"\n"
                f"{const} = {value!r}  # {name} ({code})\n"
                f"RETRY_BACKOFF_S = {rng.choice((1, 2, 5))}\n")
    if kind == "skill":
        return (f"---\nname: {subj.fact.skill or 'ops-runbook'}\n---\n"
                f"## Limits\n- {name}: {value} ({code})\n"
                f"- Ask for approval before submitting anything.\n")
    if kind == "decision":
        return rng.choice((
            f"Decision: {name} is set to {value} ({code}). Rationale: "
            f"{reason}.",
            f"ADR: adopt {value} as the {name}. Ref {code}. Agreed with "
            f"{who}.",
        ))
    if kind == "dependency":
        return rng.choice((
            f"Dependency note: {name} -> {value} ({code}).",
            f"We depend on {value} for the {name} ({code}); pinned after "
            f"{reason}.",
        ))
    return rng.choice((
        f"The {name} is {value} ({code}).",
        f"{name[0].upper() + name[1:]}: now {value} [{code}]",
        f"Changed {name} to {value} per {reason} ({code}).",
        f"Heads up: {name} moved to {value}. ref {code}",
        f"Confirmed with {who}: {name} = {value} ({code})",
        f"After {reason}, we're running the {name} at {value} ({code}).",
    ))


def query_text(rng: random.Random, subj: Subject) -> str:
    name = subj.name(rng)
    return rng.choice((
        f"What is the current {name}?",
        f"{name}?",
        f"remind me the {name}",
        f"Which value do we use for {name} right now?",
        f"what did we settle on for the {name}",
    ))


AMBIGUOUS_TEMPLATES = {
    "TTL": "what's the TTL {scope}?",
    "session limit": "what's the session limit {scope}?",
    "provider": "which provider are we using {scope}?",
    "budget": "what's the budget {scope}?",
    "plan": "what plan are we on {scope}?",
    "limit": "what's the limit {scope}?",
    "rate limit": "what's the rate limit {scope}?",
    "retention": "how long is the retention {scope}?",
    "timeout": "what's the timeout {scope}?",
    "model": "which model do we use {scope}?",
    "version": "which version are we on {scope}?",
    "threshold": "what's the threshold {scope}?",
}


# ----------------------------------------------------------------- filler
_MODULES = ("voice", "auth", "api", "workers", "memory", "billing", "web",
            "jobs", "approvals", "common")
_FILES = ("pipeline", "client", "handlers", "models", "routes", "utils",
          "retry", "session", "schema", "tasks", "queue", "events")
_SPEC_STEMS = ("onboarding", "billing", "notifications", "search", "admin",
               "analytics", "scheduler", "incident-response", "mobile",
               "permissions", "exports", "audit-log", "feature-flags")
_SKILLS = ("job-apply", "inbox-triage", "calendar-sync", "web-research",
           "form-filler", "code-review", "standup-notes", "expense-report")
_LOG_LINES = (
    "INFO auth: token refreshed for user {n}; ttl check ok",
    "WARN voice: STT partial timeout after {n} ms, retrying",
    "INFO worker: step {n} done (budget check ok)",
    "ERROR api: 502 from upstream gateway, attempt {n}",
    "INFO gradium: session opened ({n} active)",
    "DEBUG memory: retrieved {n} items for context",
    "INFO job-apply: submitted application #{n}",
    "WARN browser: navigation slow ({n} ms) on blocked-domain check",
    "INFO deploy: build {n} promoted",
    "INFO supabase: pool usage {n}%",
)
_TASKS = (
    "TODO: wire the STT fallback into the {m} pipeline",
    "Task: add retries around the {m} client ({n} failures last week)",
    "Follow-up: write tests for {m} session expiry",
    "Task: document the approval flow for {m}",
    "TODO: clean up dead code in src/{m}/",
    "Investigate flaky test in {m} (seen {n} times)",
)
_CLAIMS = (
    "The {m} service p95 latency was {n} ms in today's run.",
    "Noticed the {m} queue backs up when more than {n} jobs arrive.",
    "User mentioned they prefer short replies in the {m} flow.",
    "The {m} dashboard shows {n} errors since the last deploy.",
)
_SUMMARIES = (
    "Session summary: worked on {m}; {n} files touched, tests green.",
    "Daily recap: {m} refactor ongoing, {n} open questions.",
    "Summary of standup: {m} blocked on review, {n} tasks closed.",
)


class Filler:
    """Haystack writes without value codes."""

    def __init__(self, world: World, size: int) -> None:
        self.w = world
        self.rng = world.rng
        self.log_n = 0
        pool = max(8, size // 60)
        self.code_paths = [f"src/{self.rng.choice(_MODULES)}/"
                           f"{self.rng.choice(_FILES)}.py"
                           for _ in range(pool)]
        self.spec_paths = [f"docs/{self.rng.choice(('notes', 'runbooks', 'guides'))}/"
                           f"{self.rng.choice(_SPEC_STEMS)}.md"
                           for _ in range(max(4, pool // 2))]
        self.skill_paths = [f"skills/{s}/SKILL.md" for s in _SKILLS]

    def text_and_path(self, kind: str) -> tuple[str, str | None]:
        r = self.rng
        m = r.choice(_MODULES)
        n = r.randint(2, 999)
        if kind == "log":
            self.log_n += 1
            path = r.choice((f"logs/run-{self.log_n:04d}.log",
                             f"logs/worker-{r.choice(AGENTS)}-{self.log_n:04d}.log",
                             f"logs/deploy-{self.log_n:04d}.log"))
            lines = [r.choice(_LOG_LINES).format(n=r.randint(1, 2000))
                     for _ in range(r.randint(2, 6))]
            return "\n".join(lines), path
        if kind == "code":
            path = r.choice(self.code_paths)
            fn = r.choice(("handle", "fetch", "retry", "parse", "render"))
            return (f"# {path}\ndef {fn}_{m}(payload):\n"
                    f"    \"\"\"{fn.title()} {m} payloads.\"\"\"\n"
                    f"    return process(payload, limit={n})\n"), path
        if kind == "spec":
            path = r.choice(self.spec_paths)
            return (f"# {path.split('/')[-1][:-3].title()}\n\n"
                    f"Notes for {m}: keep the flow simple; {n} users in the "
                    f"pilot.\n"), path
        if kind == "skill":
            path = r.choice(self.skill_paths)
            return (f"---\nname: {path.split('/')[1]}\n---\n## Steps\n"
                    f"1. Read the task.\n2. Plan up to {n % 20 + 3} steps.\n"
                    f"3. Report back.\n"), path
        if kind == "task":
            return r.choice(_TASKS).format(m=m, n=n), None
        if kind == "summary":
            return r.choice(_SUMMARIES).format(m=m, n=n), None
        return r.choice(_CLAIMS).format(m=m, n=n), None


# -------------------------------------------------------------------- api
def generate(size: int, seed: int):
    """Build the full dataset for (size, seed)."""
    from .scenarios import build_dataset
    return build_dataset(size, seed)


def write_to_json(w: Write) -> dict:
    d = asdict(w)
    d["supersedes"] = list(w.supersedes)
    return d


def write_from_json(d: dict) -> Write:
    d = dict(d)
    d["supersedes"] = tuple(d.get("supersedes") or ())
    return Write(**d)


def stream_hash(ds) -> str:
    """sha256 over the public stream, queries and traces (determinism)."""
    h = hashlib.sha256()
    for ev in ds.events:
        h.update(json.dumps(ev.to_json(), sort_keys=True).encode())
    return h.hexdigest()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--size", type=int, required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    ds = generate(a.size, a.seed)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "writes.jsonl"), "w", encoding="utf-8") as f:
        for w in ds.writes:
            f.write(json.dumps(write_to_json(w)) + "\n")
    with open(os.path.join(a.out, "queries.jsonl"), "w",
              encoding="utf-8") as f:
        for q in ds.all_query_specs():
            f.write(json.dumps(q.to_json()) + "\n")
    with open(os.path.join(a.out, "sealed_truth.json"), "w",
              encoding="utf-8") as f:
        json.dump({op: asdict(s) for op, s in ds.seals.items()}, f)
    print(f"writes={len(ds.writes)} queries={len(ds.all_query_specs())} "
          f"chains={len(ds.chains)} hash={stream_hash(ds)}")


if __name__ == "__main__":
    main()
