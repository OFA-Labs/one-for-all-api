"""At-least-once outbox with leases, fencing, bounded retry and contiguous watermarks.

A crash between event commit and projection cannot lose work: the job row is
created in the same transaction as the accepted event. Jobs are idempotent by
stable key; applying the same job twice is a no-op.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..config import V3Config
from ..contracts import OutboxJob


@dataclass
class Outbox:
    cfg: V3Config
    jobs: dict[str, OutboxJob] = field(default_factory=dict)
    applied_keys: set[str] = field(default_factory=set)
    watermark: int = 0
    dead: set[str] = field(default_factory=set)

    def enqueue(self, job: OutboxJob) -> bool:
        """Idempotent by job_id. Returns True when a new job was created."""
        if job.job_id in self.jobs or job.job_id in self.applied_keys:
            return False
        self.jobs[job.job_id] = job
        return True

    def lease(self, worker_id: str, now_seq: int, limit: int = 16) -> tuple[OutboxJob, ...]:
        leased: list[OutboxJob] = []
        for job in sorted(self.jobs.values(), key=lambda j: (j.knowledge_seq, j.job_id)):
            if len(leased) >= limit:
                break
            if job.state != "pending":
                continue
            if job.attempts >= self.cfg.outbox_max_attempts:
                self.jobs[job.job_id] = job.model_copy(
                    update={"state": "dead", "last_error": "retry limit exceeded"}
                )
                self.dead.add(job.job_id)
                continue
            self.jobs[job.job_id] = job.model_copy(update={
                "state": "leased",
                "lease_owner": worker_id,
                "lease_expires_seq": now_seq + self.cfg.job_lease_ticks,
                "attempts": job.attempts + 1,
            })
            leased.append(self.jobs[job.job_id])
        return tuple(leased)

    def reclaim_expired(self, now_seq: int) -> int:
        reclaimed = 0
        for job_id, job in list(self.jobs.items()):
            if job.state == "leased" and now_seq >= job.lease_expires_seq:
                self.jobs[job_id] = job.model_copy(update={
                    "state": "pending", "lease_owner": "", "lease_expires_seq": 0,
                })
                reclaimed += 1
        return reclaimed

    def apply(self, job_id: str, worker_id: str, *, fail: bool = False) -> bool:
        """Fenced, idempotent application. Returns True if newly applied."""
        job = self.jobs.get(job_id)
        if job is None or job.state != "leased" or job.lease_owner != worker_id:
            return False
        if job.job_id in self.applied_keys:
            self.jobs[job_id] = job.model_copy(update={"state": "applied"})
            return False
        if fail:
            self.jobs[job_id] = job.model_copy(update={
                "state": "pending", "lease_owner": "", "lease_expires_seq": 0,
                "last_error": "worker failed",
            })
            return False
        self.applied_keys.add(job_id)
        self.jobs[job_id] = job.model_copy(update={"state": "applied", "lease_owner": ""})
        # Contiguous watermark: only advance across fully applied ordered jobs.
        self.applied_seq_markers.add(job.knowledge_seq)
        while self.watermark + 1 in self.applied_seq_markers:
            self.watermark += 1
        return True

    applied_seq_markers: set[int] = field(default_factory=set)

    def mark_contiguous(self, seq: int) -> None:
        self.applied_seq_markers.add(seq)

    @property
    def pending_count(self) -> int:
        return sum(1 for j in self.jobs.values() if j.state in ("pending", "leased"))

    @property
    def dead_count(self) -> int:
        return len(self.dead)
