"""Job lifecycle actions: restart, requeue, cancel, continue, and chat messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.security import sanitize_task_prompt
from server.models import Job, JobMessage, JobStatus, MessageRole, Project
from server.orchestrator import job_log_path, read_log_tail

TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
ACTIVE_STATUSES = {JobStatus.QUEUED, JobStatus.RUNNING}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_job_or_404(db: Session, job_id: str) -> Job:
    job = db.query(Job).filter(Job.job_id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _thread_root_id(job: Job) -> str:
    return job.thread_root_id or job.job_id


def seed_task_message(db: Session, job: Job) -> None:
    db.add(
        JobMessage(
            job_id=job.job_id,
            role=MessageRole.USER,
            content=job.task,
        )
    )


def add_system_message(db: Session, job_id: str, content: str) -> None:
    db.add(
        JobMessage(
            job_id=job_id,
            role=MessageRole.SYSTEM,
            content=content.strip(),
        )
    )


def get_job_messages(db: Session, job_id: str) -> list[JobMessage]:
    job = _get_job_or_404(db, job_id)
    root = _thread_root_id(job)

    thread_job_ids = [
        row.job_id
        for row in db.query(Job.job_id)
        .filter((Job.thread_root_id == root) | (Job.job_id == root))
        .order_by(Job.created_at.asc())
        .all()
    ]

    if not thread_job_ids:
        thread_job_ids = [job_id]

    return (
        db.query(JobMessage)
        .filter(JobMessage.job_id.in_(thread_job_ids))
        .order_by(JobMessage.created_at.asc())
        .all()
    )


def build_continuation_task(db: Session, job: Job, follow_up: str) -> str:
    root = _thread_root_id(job)
    history = (
        db.query(JobMessage)
        .join(Job, Job.job_id == JobMessage.job_id)
        .filter((Job.thread_root_id == root) | (Job.job_id == root))
        .order_by(JobMessage.created_at.asc())
        .all()
    )

    lines = [
        "You are continuing a previous orchestration run on this repository.",
        f"\nOriginal task:\n{job.task}",
    ]
    if history:
        lines.append("\nConversation history:")
        for message in history:
            label = message.role.value.capitalize()
            lines.append(f"[{label}]: {message.content}")
    lines.append(f"\nFollow-up instruction:\n{follow_up.strip()}")
    lines.append(
        "\nContinue from the previous work. Inspect the current repo state, "
        "respect prior changes, and address the follow-up."
    )
    return sanitize_task_prompt("\n".join(lines), max_length=12000)


def restart_job(db: Session, job_id: str) -> Job:
    source = _get_job_or_404(db, job_id)
    new_uuid = str(uuid.uuid4())
    job = Job(
        job_id=new_uuid,
        project_id=source.project_id,
        task=source.task,
        level=source.level,
        status=JobStatus.QUEUED,
        logs_path=str(job_log_path(new_uuid)),
        parent_job_id=source.job_id,
        thread_root_id=_thread_root_id(source),
    )
    db.add(job)
    db.flush()
    seed_task_message(db, job)
    add_system_message(
        db,
        new_uuid,
        f"Restarted from run {source.job_id[:8]}… (same task, fresh execution).",
    )
    db.commit()
    db.refresh(job)
    return job


def requeue_job(db: Session, job_id: str) -> Job:
    job = _get_job_or_404(db, job_id)
    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot requeue job with status {job.status.value}",
        )

    log_path = job_log_path(job.job_id)
    if log_path.is_file():
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n\n--- Requeued at {_utcnow().isoformat()} ---\n")

    job.status = JobStatus.QUEUED
    job.started_at = None
    job.finished_at = None
    job.error_message = None
    add_system_message(db, job.job_id, "Run requeued — waiting for worker.")
    db.commit()
    db.refresh(job)
    return job


def cancel_job(db: Session, job_id: str) -> Job:
    job = _get_job_or_404(db, job_id)
    if job.status not in ACTIVE_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot cancel job with status {job.status.value}",
        )

    job.status = JobStatus.CANCELLED
    job.finished_at = _utcnow()
    job.error_message = job.error_message or "Cancelled by user"
    add_system_message(db, job.job_id, "Run cancelled from the dashboard.")
    db.commit()
    db.refresh(job)
    return job


def continue_job(db: Session, job_id: str, message: str) -> Job:
    source = _get_job_or_404(db, job_id)
    if source.status == JobStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Wait for the current run to finish before continuing")

    follow_up = sanitize_task_prompt(message.strip())
    add_system_message(db, source.job_id, f"Follow-up queued: {follow_up}")

    new_uuid = str(uuid.uuid4())
    composed_task = build_continuation_task(db, source, follow_up)
    job = Job(
        job_id=new_uuid,
        project_id=source.project_id,
        task=composed_task,
        level=source.level,
        status=JobStatus.QUEUED,
        logs_path=str(job_log_path(new_uuid)),
        parent_job_id=source.job_id,
        thread_root_id=_thread_root_id(source),
    )
    db.add(job)
    db.flush()
    db.add(
        JobMessage(
            job_id=new_uuid,
            role=MessageRole.USER,
            content=follow_up,
        )
    )
    add_system_message(
        db,
        new_uuid,
        f"Continuing from run {source.job_id[:8]}…",
    )
    db.commit()
    db.refresh(job)
    return job


def record_job_outcome(db: Session, job_id: str, *, success: bool, error_message: str | None) -> None:
    job = db.query(Job).filter(Job.job_id == job_id).one_or_none()
    if job is None or job.status == JobStatus.CANCELLED:
        return

    tail = read_log_tail(job_log_path(job_id), max_lines=40)
    if success:
        summary = "Run completed successfully."
        if tail:
            summary = f"Run completed successfully.\n\nLast output:\n{tail}"
        add_system_message(db, job_id, summary)
    else:
        detail = error_message or "Run failed."
        if tail:
            detail = f"{detail}\n\nLast output:\n{tail}"
        add_system_message(db, job_id, detail)
