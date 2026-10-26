from __future__ import annotations

import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable

_QUEUE: "queue.Queue[str]" = queue.Queue()
_JOBS: dict[str, "Job"] = {}
_LOCK = threading.Lock()
_WORKER: threading.Thread | None = None


@dataclass
class Job:
    id: str
    kind: str
    ref: dict
    status: str = "queued"
    progress: float = 0.0
    step: str = ""
    error: str | None = None
    result: dict | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "ref": self.ref,
            "status": self.status,
            "progress": round(self.progress, 3),
            "step": self.step,
            "error": self.error,
            "result": self.result,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def update(job_id: str, *, progress: float | None = None, step: str | None = None, status: str | None = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        if progress is not None:
            job.progress = max(job.progress, min(1.0, progress))
        if step is not None:
            job.step = step
        if status is not None:
            job.status = status
        job.updated_at = time.time()


def get(job_id: str) -> Job | None:
    with _LOCK:
        return _JOBS.get(job_id)


def find_for(ref: str) -> Job | None:
    with _LOCK:
        for job in _JOBS.values():
            if job.ref.get("chapter_id") == ref and job.status in ("queued", "running"):
                return job
    return None


def _worker_loop() -> None:
    while True:
        job_id = _QUEUE.get()
        job = get(job_id)
        if not job:
            continue
        fn = _RUNNERS.get(job.kind)
        update(job_id, status="running", step="starting")
        try:
            result = fn(job)
            with _LOCK:
                job.result = result
                job.progress = 1.0
                job.status = "done"
                job.step = "done"
                job.updated_at = time.time()
        except Exception as exc:  # noqa: BLE001 - surfaced to the client
            with _LOCK:
                job.status = "error"
                job.error = f"{type(exc).__name__}: {exc}"
                job.step = "failed"
                job.updated_at = time.time()
            traceback.print_exc()
        finally:
            _QUEUE.task_done()


_RUNNERS: dict[str, Callable[[Job], dict]] = {}


def runner(kind: str):
    def deco(fn: Callable[[Job], dict]):
        _RUNNERS[kind] = fn
        return fn

    return deco


def start() -> None:
    global _WORKER
    if _WORKER and _WORKER.is_alive():
        return
    _WORKER = threading.Thread(target=_worker_loop, name="composer-worker", daemon=True)
    _WORKER.start()


def submit(kind: str, ref: dict) -> Job:
    job = Job(id=uuid.uuid4().hex[:12], kind=kind, ref=ref)
    with _LOCK:
        _JOBS[job.id] = job
    _QUEUE.put(job.id)
    start()
    return job
