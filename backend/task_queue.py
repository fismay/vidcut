from __future__ import annotations

import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from backend.models import JobCreatedResponse, JobFileInfo, JobLogEntry, JobStatusResponse
from backend.utils import clamp_progress

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    job_id: str
    title: str
    video_id: str
    video_url: str
    add_subtitles: bool = True
    status: str = "queued"
    stage: str = "queued"
    progress: float = 0.0
    message: str = "Task created"
    error: str | None = None
    files: list[JobFileInfo] = field(default_factory=list)
    logs: list[JobLogEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    current_part: int = 0
    total_parts: int = 0


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._processor = None

    def set_processor(self, processor: object) -> None:
        self._processor = processor

    def start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        self._worker = threading.Thread(target=self._worker_loop, name="video-worker", daemon=True)
        self._worker.start()
        logger.info("Background worker started")

    def create_job(self, *, title: str, video_id: str, video_url: str, add_subtitles: bool) -> JobCreatedResponse:
        job_id = uuid.uuid4().hex
        record = JobRecord(
            job_id=job_id,
            title=title,
            video_id=video_id,
            video_url=video_url,
            add_subtitles=add_subtitles,
        )
        record.logs.append(JobLogEntry(timestamp=datetime.utcnow(), level="info", message="Queueing task"))

        with self._lock:
            self._jobs[job_id] = record

        self._queue.put(job_id)
        return JobCreatedResponse(job_id=job_id, status=record.status)

    def _worker_loop(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self.mark_running(job_id, "Preparing video processing pipeline")
                if self._processor is None:
                    raise RuntimeError("Job processor is not configured")
                self._processor.process(job_id)
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.exception("Unhandled worker error for job %s", job_id)
                self.fail(job_id, f"Unhandled error: {exc}")
            finally:
                self._queue.task_done()

    def _touch(self, record: JobRecord) -> None:
        record.updated_at = datetime.utcnow()

    def get_record(self, job_id: str) -> JobRecord:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return self._jobs[job_id]

    def get_status(self, job_id: str) -> JobStatusResponse:
        record = self.get_record(job_id)
        return JobStatusResponse(
            job_id=record.job_id,
            title=record.title,
            video_id=record.video_id,
            add_subtitles=record.add_subtitles,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            message=record.message,
            error=record.error,
            files=record.files,
            logs=record.logs[-25:],
            created_at=record.created_at,
            updated_at=record.updated_at,
            current_part=record.current_part,
            total_parts=record.total_parts,
        )

    def set_total_parts(self, job_id: str, total_parts: int) -> None:
        record = self.get_record(job_id)
        with self._lock:
            record.total_parts = total_parts
            self._touch(record)

    def set_title(self, job_id: str, title: str) -> None:
        record = self.get_record(job_id)
        with self._lock:
            record.title = title
            self._touch(record)

    def mark_running(self, job_id: str, message: str) -> None:
        self.update(job_id, status="running", stage="starting", progress=1, message=message)

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        current_part: int | None = None,
    ) -> None:
        record = self.get_record(job_id)
        with self._lock:
            if status is not None:
                record.status = status
            if stage is not None:
                record.stage = stage
            if progress is not None:
                record.progress = clamp_progress(progress)
            if message is not None:
                record.message = message
            if current_part is not None:
                record.current_part = current_part
            self._touch(record)

    def add_log(self, job_id: str, message: str, *, level: str = "info") -> None:
        record = self.get_record(job_id)
        entry = JobLogEntry(timestamp=datetime.utcnow(), level=level, message=message)
        with self._lock:
            record.logs.append(entry)
            self._touch(record)

    def add_file(self, job_id: str, file_info: JobFileInfo) -> None:
        record = self.get_record(job_id)
        with self._lock:
            record.files.append(file_info)
            self._touch(record)

    def complete(self, job_id: str, message: str, *, partial: bool = False) -> None:
        status = "partial" if partial else "completed"
        self.update(job_id, status=status, stage="completed", progress=100, message=message)

    def fail(self, job_id: str, error: str) -> None:
        record = self.get_record(job_id)
        with self._lock:
            record.status = "failed"
            record.stage = "failed"
            record.progress = clamp_progress(record.progress)
            record.message = "Task finished with an error"
            record.error = error
            self._touch(record)
            record.logs.append(JobLogEntry(timestamp=datetime.utcnow(), level="error", message=error))
