"""Async background worker that polls and executes queued jobs."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from core.models import AgentPreset
from server.config import PROJECT_ROOT, get_max_concurrent_jobs
from server.database import SessionLocal
from server.job_service import add_system_message, record_job_outcome
from server.models import Job, JobStatus, Project
from server.orchestrator import build_command, job_log_path, write_log_header
from server.webhook_callback import build_callback_payload, notify_job_finished_with_payload

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 1.0
_running_job_ids: set[str] = set()
_worker_task: asyncio.Task[None] | None = None
_shutdown_event: asyncio.Event | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _count_running(db: Session) -> int:
    return db.query(Job).filter(Job.status == JobStatus.RUNNING).count()


def _fetch_next_queued(db: Session, limit: int) -> list[Job]:
    return (
        db.query(Job)
        .filter(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at.asc())
        .limit(limit)
        .all()
    )


def _handle_log_line(db: Session, job_id: str, line: str) -> None:
    """Detect structured orchestrator events and mirror them to job messages."""
    trimmed = line.strip()
    if not trimmed.startswith("{"):
        return
    try:
        payload = json.loads(trimmed)
    except json.JSONDecodeError:
        return
    if payload.get("event") != "model_switch":
        return
    from_model = payload.get("from_model", "?")
    to_model = payload.get("to_model", "?")
    reason = payload.get("reason", "agent_failure")
    add_system_message(
        db,
        job_id,
        f"Model failover: {from_model} → {to_model} ({reason})",
    )


async def _run_subprocess(
    job_id: str,
    repo_url: str,
    task: str,
    level: str,
    preset: str,
    model: str | None,
    log_path_str: str,
) -> None:
    log_path = job_log_path(job_id)
    cmd = build_command(repo_url, task, level, preset, model=model)
    started_at = _utcnow()
    write_log_header(log_path, cmd, started_at)

    exit_code = -1
    error_message: str | None = None

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(PROJECT_ROOT),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        assert proc.stdout is not None
        db = SessionLocal()
        try:
            with log_path.open("a", encoding="utf-8") as log_file:
                async for raw_line in proc.stdout:
                    line = raw_line.decode("utf-8", errors="replace")
                    log_file.write(line)
                    log_file.flush()
                    _handle_log_line(db, job_id, line)
                exit_code = await proc.wait()
                log_file.write(f"\n\nExit code: {exit_code}\n")
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        logger.exception("Job %s failed with exception", job_id)
        error_message = str(exc)
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\nException: {exc}\n")
    finally:
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.job_id == job_id).one_or_none()
            if job is None:
                return
            if job.status == JobStatus.CANCELLED:
                return
            job.finished_at = _utcnow()
            job.logs_path = log_path_str
            if error_message:
                job.status = JobStatus.FAILED
                job.error_message = error_message
                record_job_outcome(db, job_id, success=False, error_message=error_message)
            elif exit_code == 0:
                job.status = JobStatus.COMPLETED
                record_job_outcome(db, job_id, success=True, error_message=None)
            else:
                job.status = JobStatus.FAILED
                job.error_message = f"Process exited with code {exit_code}"
                record_job_outcome(
                    db,
                    job_id,
                    success=False,
                    error_message=job.error_message,
                )
            project = db.query(Project).filter(Project.id == job.project_id).one_or_none()
            webhook_payload: tuple[str, dict] | None = None
            if project and job.status in {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            }:
                settings = project.settings or {}
                url = settings.get("webhook_url")
                if isinstance(url, str) and url.strip():
                    webhook_payload = (url.strip(), build_callback_payload(job, project))
            db.commit()
            if webhook_payload is not None:
                url, payload = webhook_payload
                asyncio.create_task(notify_job_finished_with_payload(url, payload, job.job_id))
        finally:
            db.close()
            _running_job_ids.discard(job_id)


async def _dispatch_job(job: Job) -> None:
    db = SessionLocal()
    try:
        db_job = (
            db.query(Job)
            .filter(
                Job.job_id == job.job_id,
                Job.status == JobStatus.QUEUED,
            )
            .one_or_none()
        )
        if db_job is None:
            return

        project = db.query(Project).filter(Project.id == db_job.project_id).one()
        log_path = job_log_path(db_job.job_id)
        log_path_str = str(log_path)

        db_job.status = JobStatus.RUNNING
        db_job.started_at = _utcnow()
        db_job.logs_path = log_path_str
        db.commit()

        repo_url = project.repo_url
        task = db_job.task
        level = db_job.level
        preset = AgentPreset.to_value(db_job.preset)
        model = db_job.model
        job_id = db_job.job_id
    finally:
        db.close()

    logger.info(
        "Starting job %s for project_id=%s preset=%s model=%s",
        job_id,
        job.project_id,
        preset,
        model,
    )
    _running_job_ids.add(job_id)
    asyncio.create_task(
        _run_subprocess(job_id, repo_url, task, level, preset, model, log_path_str)
    )


async def worker_loop() -> None:
    max_concurrent = get_max_concurrent_jobs()
    logger.info("Job worker started (max_concurrency=%s)", max_concurrent)

    while _shutdown_event is None or not _shutdown_event.is_set():
        try:
            db = SessionLocal()
            try:
                running_count = _count_running(db)
                available = max_concurrent - running_count - len(_running_job_ids)
                if available > 0:
                    queued = _fetch_next_queued(db, available)
                    for job in queued:
                        if job.job_id in _running_job_ids:
                            continue
                        await _dispatch_job(job)
            finally:
                db.close()
        except Exception:
            logger.exception("Worker poll cycle failed")

        try:
            await asyncio.wait_for(_shutdown_event.wait(), timeout=POLL_INTERVAL_SECONDS)
            break
        except TimeoutError:
            continue

    logger.info("Job worker stopped")


def is_worker_running() -> bool:
    return _worker_task is not None and not _worker_task.done()


async def start_worker() -> None:
    global _worker_task, _shutdown_event
    if _worker_task is not None and not _worker_task.done():
        return
    _shutdown_event = asyncio.Event()
    _worker_task = asyncio.create_task(worker_loop())


async def stop_worker() -> None:
    global _worker_task, _shutdown_event
    if _shutdown_event is not None:
        _shutdown_event.set()
    if _worker_task is not None:
        await _worker_task
        _worker_task = None
    _shutdown_event = None
