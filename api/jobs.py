"""
api/jobs.py — Sequential job queue for video generation.

Why sequential (one worker thread, not a pool):
  1. qa_mode/config.py (and story_mode's) are plain modules — config_utils
     restores+overrides them per job. Running two jobs concurrently would
     race on that shared module state.
  2. TTS backends (esp. xtts) load multi-GB models onto the GPU/MPS device.
     Running them concurrently on a single MacBook is more likely to OOM
     than to save time.

If you need throughput later, the clean upgrade path is one worker process
per TTS backend/model already loaded, or a real task queue (Celery/RQ) with
a worker pool sized to available memory — not silently making this queue
concurrent.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from api import config_utils

log = logging.getLogger("api.jobs")


@dataclass
class Job:
    job_id: str
    qa_pairs: list[tuple[str, str]]
    title: str
    overrides: dict
    keep_temp: bool = False
    status: str = "queued"          # queued | running | done | failed
    error: Optional[str] = None
    result: Optional[dict] = None
    created_at: float = field(default_factory=time.time)
    batch_id: Optional[str] = None
    part_number: Optional[int] = None


@dataclass
class Batch:
    batch_id: str
    name: str
    job_ids: list[str]
    total_questions: int
    questions_per_part: int
    created_at: float = field(default_factory=time.time)


class JobManager:
    def __init__(self) -> None:
        self._queue: "queue.Queue[Job]" = queue.Queue()
        self._jobs: dict[str, Job] = {}
        self._batches: dict[str, Batch] = {}
        self._lock = threading.Lock()
        self._cfg_snapshot: Optional[dict] = None
        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

    # ── Public API ──────────────────────────────────────────────────────
    def submit(self, qa_pairs: list[tuple[str, str]], title: str,
               overrides: dict, keep_temp: bool = False,
               batch_id: Optional[str] = None, part_number: Optional[int] = None) -> Job:
        job = Job(job_id=uuid.uuid4().hex[:12], qa_pairs=qa_pairs, title=title,
                  overrides=overrides, keep_temp=keep_temp,
                  batch_id=batch_id, part_number=part_number)
        with self._lock:
            self._jobs[job.job_id] = job
        self._queue.put(job)
        log.info("Job %s queued (%d Q/A pairs)", job.job_id, len(qa_pairs))
        return job

    def submit_batch(self, qa_pairs: list[tuple[str, str]], name: str,
                      questions_per_part: int, overrides: dict,
                      keep_temp: bool = False) -> Batch:
        """
        Split qa_pairs into chunks of `questions_per_part` and submit one
        video-generation job per chunk, titled f"{name}_part{n}". All chunks
        are queued immediately; they run one-at-a-time like any other job.
        """
        if questions_per_part < 1:
            raise ValueError("questions_per_part must be >= 1")
        if not qa_pairs:
            raise ValueError("qa_pairs must not be empty")

        batch_id = uuid.uuid4().hex[:12]
        job_ids: list[str] = []
        chunks = [
            qa_pairs[i:i + questions_per_part]
            for i in range(0, len(qa_pairs), questions_per_part)
        ]
        for part_number, chunk in enumerate(chunks, start=1):
            job = self.submit(
                qa_pairs=chunk,
                title=f"{name}_part{part_number}",
                overrides=overrides,
                keep_temp=keep_temp,
                batch_id=batch_id,
                part_number=part_number,
            )
            job_ids.append(job.job_id)

        batch = Batch(
            batch_id=batch_id, name=name, job_ids=job_ids,
            total_questions=len(qa_pairs), questions_per_part=questions_per_part,
        )
        with self._lock:
            self._batches[batch_id] = batch
        log.info("Batch %s queued: %d parts (%d questions / %d per part)",
                  batch_id, len(chunks), len(qa_pairs), questions_per_part)
        return batch

    def get_batch(self, batch_id: str) -> Optional[Batch]:
        with self._lock:
            return self._batches.get(batch_id)

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def queue_position(self, job_id: str) -> Optional[int]:
        """1-based position in the pending queue, or None if not queued."""
        with self._lock:
            pending = [j.job_id for j in self._jobs.values() if j.status == "queued"]
        if job_id in pending:
            return pending.index(job_id) + 1
        return None

    # ── Worker ───────────────────────────────────────────────────────────
    def _worker_loop(self) -> None:
        from qa_mode import config as qa_cfg
        self._cfg_snapshot = config_utils.snapshot(qa_cfg)

        while True:
            job = self._queue.get()
            job.status = "running"
            log.info("Job %s running", job.job_id)
            try:
                job.result = self._run_job(job, qa_cfg)
                job.status = "done"
                log.info("Job %s done -> %s", job.job_id, job.result.get("video_path"))
            except Exception as exc:  # noqa: BLE001 - surface any failure to the API caller
                log.exception("Job %s failed", job.job_id)
                job.status = "failed"
                job.error = str(exc)
            finally:
                # Always restore shared config module to defaults so the
                # next job starts clean, even if this one raised mid-way.
                config_utils.restore(qa_cfg, self._cfg_snapshot)

    def _run_job(self, job: Job, qa_cfg) -> dict:
        config_utils.restore(qa_cfg, self._cfg_snapshot)
        config_utils.apply_overrides(qa_cfg, job.overrides)

        from qa_mode.loader import build_qa_segments
        from qa_mode.runner import run_from_segments

        segments = build_qa_segments(job.qa_pairs, qa_cfg)
        return run_from_segments(
            segments, title=job.title, cfg=qa_cfg, keep_temp=job.keep_temp,
        )


# Module-level singleton — one queue/worker per API process.
manager = JobManager()
