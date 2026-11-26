"""Deterministic demo history: the seven sample records the frontend preview already shows.

    python -m history.seed --user demo --reset

Content is hard-coded here (copied from the frontend's sample scenarios), never imported from
it. Every record is ``is_sample=1`` and fictional: no real website or account was used. Seeding
goes through ``HistoryStore.ingest`` so it applies the same validation as ``POST /v1/tasks``.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime

from .config import load_config
from .errors import HistoryError
from .models import TaskIn
from .store import HistoryStore

MIN = 60_000


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso).timestamp()) * 1000


def _h(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode()).hexdigest()


# Block lengths match the frontend calendar's per-scenario durations (minutes).
_DURATION_MIN = {"jobs": 70, "social": 80, "decline": 20}

PR_PLAN = {
    "steps": ["Read PR #142 in acme/voice-kit",
              "Prepare a note for the existing #engineering channel",
              "Wait for your approval", "Send and verify the message"],
    "sites": ["github.com", "slack.com"], "recipients": ["#engineering"],
}
JOBS_PLAN = {
    "steps": ["Confirm your role, salary and resume facts",
              "Compare five sample ML engineer roles",
              "Clarify relocation and prepare the form",
              "Review the resume and declarations",
              "Submit in the Playground and check the receipt"],
    "sites": ["playground.one-for-all.test"], "recipients": [],
}
SOCIAL_PLAN = {
    "steps": ["Confirm the sample source video and real accounts",
              "Prepare four platform-specific drafts",
              "Review every recipient and exact value",
              "Commit selected items one at a time",
              "Reload and verify each result"],
    "sites": ["youtube.com", "linkedin.com", "x.com", "slack.com"],
    "recipients": ["#side-projects"],
}
RESEARCH_PLAN = {
    "steps": ["Open three public sources in isolated browsers",
              "Normalize units and note assumptions", "Compare illustrative prices",
              "Report sources and unknowns"],
    "sites": ["public-source-a.test", "public-source-b.test", "public-source-c.test"],
    "recipients": [],
}
DECLINE_PLAN = {"steps": ["Screen request before tools",
                          "Decline fake identities and fake engagement"],
                "sites": [], "recipients": []}

SLACK_TEXT = ("Hey team, PR #142 is ready for review. It adds interruption handling to the "
              "voice pipeline. Could someone take a look when they have a moment?")


def _base(task_id, scenario, title, subtitle, goal, plan, occurred, state, user, **extra):
    minutes = _DURATION_MIN.get(scenario, 45)
    return dict(task_id=task_id, user_id=user, goal=goal, title=title, subtitle=subtitle,
                scenario=scenario, plan=plan, state=state, is_sample=True,
                occurred_at=_ms(occurred), created_at=_ms(occurred) - minutes * MIN,
                ended_at=_ms(occurred), **extra)


def _events(created: int, *items: tuple[int, str, str]) -> list[dict]:
    return [{"seq": n, "at": created + minute * MIN, "type": kind, "message": message}
            for n, (minute, kind, message) in enumerate(items, 1)]


def seed_records(user: str) -> list[TaskIn]:
    out: list[dict] = []

    pr = _base("sample-pr", "pr", "A gentle nudge for PR #142", "GitHub → Slack",
               "Check PR #142. If it isn't merged, ask the team on Slack to review it.",
               PR_PLAN, "2026-11-16T10:24:00+05:30", "completed", user,
               tier="A", evidence_status="verified", gate_reason="Level 2 · send on the user's "
               "behalf", summary="Message sent and read back.",
               result_url="https://slack.test/archives/sample")
    c = pr["created_at"]
    pr.update(
        events=_events(c, (0, "task.started", "Task started."),
                       (5, "plan.frozen", "Plan frozen: 4 steps, 2 sites."),
                       (12, "page.read", "Read PR #142 in acme/voice-kit."),
                       (20, "draft.prepared", "Prepared a note for #engineering."),
                       (28, "approval.granted", "You approved the exact message."),
                       (36, "commit.sent", "Message sent to #engineering."),
                       (44, "evidence.verified", "Message read back at revision 1.")),
        evidence=dict(tier="A", status="verified", item_id="slack-msg-sample-142",
                      url="https://slack.test/archives/sample",
                      readback="Message visible in #engineering at revision 1.",
                      snapshot_hash=_h("sample-pr:snapshot"), captured_at=c + 43 * MIN,
                      verified_at=c + 44 * MIN),
        ledger=[dict(idempotency_key=f"slack:send:#engineering:{_h('sample-pr:payload')[:20]}",
                     site="slack.com", target="#engineering", action="send_message",
                     payload_hash=_h("sample-pr:payload"), state="verified",
                     created_at=c + 29 * MIN,
                     transitions=[
                         dict(seq=1, at=c + 29 * MIN, to="intent", note="before commit"),
                         dict(seq=2, at=c + 36 * MIN, **{"from": "intent"}, to="committed",
                              note="click acknowledged"),
                         dict(seq=3, at=c + 44 * MIN, **{"from": "committed"}, to="verified",
                              note="read back")])],
        approvals=[dict(approval_id="sample-pr:ap:1", page_url="https://slack.test/archives/sample",
                        plan_version=1, payload_hash=_h("sample-pr:payload"),
                        exact_text=SLACK_TEXT, decision="approved", decided_at=c + 28 * MIN,
                        expires_at=c + 40 * MIN)])
    out.append(pr)

    jobs = _base("sample-jobs", "jobs", "ML engineer roles in NCR", "Playground job board",
                 "Find five ML engineer jobs above 8 LPA and prepare the best application "
                 "using my resume.", JOBS_PLAN, "2026-11-16T09:42:00+05:30", "waiting", user,
                 summary="Waiting for your answer about relocation before preparing the form.")
    c = jobs["created_at"]
    jobs["events"] = _events(c, (0, "task.started", "Task started."),
                             (6, "plan.frozen", "Plan frozen: 5 steps, 1 site."),
                             (30, "comparison.ready", "Compared five sample roles."),
                             (60, "question.asked", "Asked: which locations are acceptable?"))
    out.append(jobs)

    research = _base("sample-research", "research", "Three voices, one comparison",
                     "Public research",
                     "Compare three text-to-speech providers per million characters.",
                     RESEARCH_PLAN, "2026-11-15T18:10:00+05:30", "completed", user,
                     tier="A", evidence_status="verified",
                     summary="Three illustrative prices compared; sources and unknowns listed.",
                     result_url="https://playground.one-for-all.test/reports/sample")
    c = research["created_at"]
    research.update(
        events=_events(c, (0, "task.started", "Task started."),
                       (4, "plan.frozen", "Plan frozen: 4 steps, 3 sites."),
                       (15, "page.read", "Read three public sources in isolated browsers."),
                       (30, "report.drafted", "Normalized units and noted assumptions."),
                       (44, "evidence.verified", "Comparison read back with sources.")),
        evidence=dict(tier="A", status="verified", item_id="report-sample-tts",
                      url="https://playground.one-for-all.test/reports/sample",
                      readback="Comparison table read back with three sources.",
                      snapshot_hash=_h("sample-research:snapshot"), captured_at=c + 43 * MIN,
                      verified_at=c + 44 * MIN))
    out.append(research)

    social = _base("sample-social", "social", "Share the voice-agent demo",
                   "4 genuine-account drafts",
                   "Share my brother's newest video from accounts that are really mine.",
                   SOCIAL_PLAN, "2026-11-15T15:36:00+05:30", "completed", user,
                   tier="B", evidence_status="submitted", gate_reason="Level 2 · post on the "
                   "user's behalf", summary="Three of four drafts submitted. Not yet confirmed.")
    c = social["created_at"]
    sites = [("youtube.com", "comment", "the sample video"), ("linkedin.com", "post", "connections"),
             ("x.com", "post", "followers")]
    social.update(
        events=_events(c, (0, "task.started", "Task started."),
                       (6, "plan.frozen", "Plan frozen: 5 steps, 4 sites."),
                       (20, "draft.prepared", "Prepared four platform-specific drafts."),
                       (40, "approval.granted", "You approved three drafts and kept one."),
                       (55, "commit.sent", "Submitted three drafts one at a time."),
                       (75, "evidence.held", "Confirmation text seen; items not read back.")),
        evidence=dict(tier="B", status="submitted",
                      readback="Confirmation text seen; the created items were not read back.",
                      snapshot_hash=_h("sample-social:snapshot"), captured_at=c + 74 * MIN),
        ledger=[dict(idempotency_key=f"{site}:{action}:{_h('sample-social:' + site)[:20]}",
                     site=site, target=target, action=action,
                     payload_hash=_h("sample-social:" + site), state="committed",
                     created_at=c + (45 + i * 5) * MIN,
                     transitions=[
                         dict(seq=1, at=c + (45 + i * 5) * MIN, to="intent"),
                         dict(seq=2, at=c + (47 + i * 5) * MIN, **{"from": "intent"},
                              to="committed", note="submitted, not read back")])
                for i, (site, action, target) in enumerate(sites)],
        approvals=[dict(approval_id=f"sample-social:ap:{i + 1}", page_url=f"https://{site}.test/",
                        plan_version=1, payload_hash=_h("sample-social:" + site),
                        exact_text=f"Approved draft for {site}.", decision="approved",
                        decided_at=c + 40 * MIN, expires_at=c + 60 * MIN)
                   for i, (site, _a, _t) in enumerate(sites)])
    out.append(social)

    refusal = _base("sample-refusal", "decline", "Fake-account request",
                    "Declined before any tools",
                    "Create fake accounts and use all of them to like the same video.",
                    DECLINE_PLAN, "2026-11-15T14:20:00+05:30", "declined", user,
                    summary="Declined before any tools ran.")
    refusal["events"] = _events(refusal["created_at"],
                                (0, "task.declined",
                                 "Declined: fake identities and fake engagement. No tools ran."))
    out.append(refusal)

    paused = _base("sample-paused", "jobs", "Prepare a job application",
                   "Paused for clarification",
                   "Find five ML engineer jobs above 8 LPA and prepare the best application "
                   "using my resume.", JOBS_PLAN, "2026-11-14T11:08:00+05:30", "paused", user,
                   summary="Paused at a checkpoint; nothing was submitted.")
    c = paused["created_at"]
    paused["events"] = _events(c, (0, "task.started", "Task started."),
                               (8, "plan.frozen", "Plan frozen: 5 steps, 1 site."),
                               (45, "checkpoint.saved", "Saved a resumable checkpoint."),
                               (60, "task.paused", "You paused the task."))
    out.append(paused)

    unknown = _base("sample-unknown", "pr", "Check a message receipt",
                    "Outcome requires inspection",
                    "Check that the message sent to #engineering was delivered.",
                    PR_PLAN, "2026-11-14T10:17:00+05:30", "unknown", user, tier="unknown",
                    evidence_status="unknown", gate_reason="Level 2 · send on the user's behalf",
                    summary="The page went offline right after the send click.")
    c = unknown["created_at"]
    unknown.update(
        events=_events(c, (0, "task.started", "Task started."),
                       (10, "approval.granted", "You approved the exact message."),
                       (20, "commit.started", "Clicked send; the page then went offline."),
                       (40, "evidence.unknown", "No read-back could be captured.")),
        evidence=dict(tier="unknown", status="unknown",
                      readback="No read-back was captured after the commit.",
                      captured_at=c + 40 * MIN),
        ledger=[dict(idempotency_key=f"slack:send:#engineering:{_h('sample-unknown:payload')[:20]}",
                     site="slack.com", target="#engineering", action="send_message",
                     payload_hash=_h("sample-unknown:payload"), state="intent",
                     created_at=c + 18 * MIN,
                     transitions=[dict(seq=1, at=c + 18 * MIN, to="intent",
                                       note="before commit; never retried")])],
        approvals=[dict(approval_id="sample-unknown:ap:1", page_url="https://slack.test/archives/x",
                        plan_version=1, payload_hash=_h("sample-unknown:payload"),
                        exact_text=SLACK_TEXT, decision="expired", decided_at=c + 10 * MIN,
                        expires_at=c + 25 * MIN, note="expired before the outcome was known")])
    out.append(unknown)

    return [TaskIn.model_validate(record) for record in out]


def seed_user(store: HistoryStore, user: str, *, reset: bool, now: int) -> dict:
    """Seeds one user. Returns counts only (never content)."""
    removed = store.delete_samples() if reset else 0
    created = unchanged = conflicts = 0
    for snapshot in seed_records(user):
        try:
            result = store.ingest(snapshot, now=now)
        except HistoryError as error:
            if error.status != 409:
                raise
            conflicts += 1
            continue
        if result.body["created"]:
            created += 1
        else:
            unchanged += 1
    return {"removed": removed, "created": created, "unchanged": unchanged,
            "conflicts": conflicts}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m history.seed",
                                     description="Seed the seven fictional demo records.")
    parser.add_argument("--user", action="append", required=True,
                        help="user id to seed (repeatable)")
    parser.add_argument("--reset", action="store_true",
                        help="first delete this user's demo (is_sample) rows; real rows are kept")
    parser.add_argument("--data-dir", help="override HISTORY_DATA_DIR")
    args = parser.parse_args(argv)
    cfg = load_config()
    data_dir = args.data_dir or cfg["data_dir"]
    import time

    now = int(time.time() * 1000)
    status = 0
    for user in args.user:
        store = HistoryStore(data_dir, cfg, user)
        try:
            counts = seed_user(store, user, reset=args.reset, now=now)
        finally:
            store.close()
        print(f"seeded user={user!r}: {counts}")
        if counts["conflicts"]:
            print("  some demo rows differ from the stored versions; re-run with --reset",
                  file=sys.stderr)
            status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
