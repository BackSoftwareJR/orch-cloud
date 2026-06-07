"""Job lifecycle actions: restart, requeue, cancel, continue, auto-fix, and chat messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from core.models import AgentPreset
from core.presets.registry import resolve_model
from core.security import sanitize_task_prompt
from server.models import Job, JobMessage, JobStatus, MessageRole, Project
from server.orchestrator import job_log_path, read_log_tail

TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
ACTIVE_STATUSES = {JobStatus.QUEUED, JobStatus.RUNNING}

_TEST_FAILURE_MARKERS = (
    "tests failed",
    "test failed",
    "validation failed",
    "checks failed",
    "medium task failed",
    "exit: non-zero",
    "failed after",
    "pytest",
    "npm err",
    "error:",
)

# Must stay within core.security.sanitize_task_prompt default (CLI TaskRequest limit).
_MAX_CONTINUATION_LENGTH = 8000
_MAX_HISTORY_MESSAGES = 10
_MAX_ERROR_EXCERPT_CHARS = 2000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _job_preset_value(preset: str | AgentPreset | None) -> str:
    """Store and pass canonical preset strings, not enum reprs."""
    return AgentPreset.to_value(preset)


def _job_model_value(job: Job) -> str:
    """Return persisted model or resolve from preset for legacy rows."""
    return resolve_model(job.preset, job.model)


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


def _truncate_with_ellipsis(text: str, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= 3:
        return cleaned[:max_chars]
    return cleaned[: max_chars - 3].rstrip() + "..."


def build_continuation_task(db: Session, job: Job, follow_up: str) -> str:
    root = _thread_root_id(job)
    history = (
        db.query(JobMessage)
        .join(Job, Job.job_id == JobMessage.job_id)
        .filter((Job.thread_root_id == root) | (Job.job_id == root))
        .order_by(JobMessage.created_at.asc())
        .all()
    )

    follow_up_text = follow_up.strip()
    header = "You are continuing a previous orchestration run on this repository."
    footer = (
        "\nContinue from the previous work. Inspect the current repo state, "
        "respect prior changes, and address the follow-up."
    )

    max_messages = min(_MAX_HISTORY_MESSAGES, len(history)) if history else 0
    per_message_cap = 500
    original_cap = 1500
    follow_up_cap = 2000

    while True:
        recent = history[-max_messages:] if max_messages else []
        history_lines = [
            f"[{message.role.value.capitalize()}]: "
            f"{_truncate_with_ellipsis(message.content, per_message_cap)}"
            for message in recent
        ]
        original = _truncate_with_ellipsis(job.task, original_cap)
        follow = _truncate_with_ellipsis(follow_up_text, follow_up_cap)

        parts = [header, f"\nOriginal task:\n{original}"]
        if history_lines:
            parts.append("\nConversation history (most recent):")
            parts.extend(history_lines)
        parts.append(f"\nFollow-up instruction:\n{follow}")
        parts.append(footer)
        composed = "\n".join(parts)

        if len(composed) <= _MAX_CONTINUATION_LENGTH:
            return sanitize_task_prompt(composed)

        if max_messages > 0:
            max_messages -= 1
            continue
        if per_message_cap > 100:
            per_message_cap = max(100, per_message_cap // 2)
            max_messages = min(_MAX_HISTORY_MESSAGES, len(history)) if history else 0
            continue
        if follow_up_cap > 200:
            follow_up_cap = max(200, follow_up_cap // 2)
            max_messages = min(_MAX_HISTORY_MESSAGES, len(history)) if history else 0
            continue
        if original_cap > 200:
            original_cap = max(200, original_cap // 2)
            max_messages = min(_MAX_HISTORY_MESSAGES, len(history)) if history else 0
            continue

        return sanitize_task_prompt(
            _truncate_with_ellipsis(composed, _MAX_CONTINUATION_LENGTH)
        )


def extract_test_errors_from_log(
    log_text: str | None,
    *,
    max_lines: int = 80,
    max_chars: int = _MAX_ERROR_EXCERPT_CHARS,
) -> str:
    if not log_text:
        return "No log output available — inspect the repository and fix failing checks."

    lines = log_text.splitlines()
    error_lines = [
        line
        for line in lines
        if any(marker in line.lower() for marker in _TEST_FAILURE_MARKERS)
    ]
    selected = error_lines[-max_lines:] if error_lines else lines[-max_lines:]
    excerpt = "\n".join(selected).strip()
    if not excerpt:
        excerpt = "\n".join(lines[-max_lines:]).strip()
    return _truncate_with_ellipsis(excerpt, max_chars)


def can_auto_fix_job(job: Job) -> bool:
    if job.status != JobStatus.FAILED:
        return False
    log_path = job_log_path(job.job_id)
    tail = read_log_tail(log_path, max_lines=200) or ""
    combined = f"{job.error_message or ''}\n{tail}".lower()
    if "process exited with code" in combined or "medium task failed" in combined:
        return True
    return any(marker in combined for marker in _TEST_FAILURE_MARKERS)


def build_auto_fix_task(db: Session, job: Job) -> str:
    log_path = job_log_path(job.job_id)
    tail = read_log_tail(log_path, max_lines=200)
    errors = extract_test_errors_from_log(tail)
    follow_up = (
        "Auto-fix: the previous run failed validation after max retries.\n\n"
        f"Failure summary:\n{job.error_message or 'Run failed'}\n\n"
        f"Test/check output:\n{errors}\n\n"
        "Fix the root cause, keep changes minimal, and ensure checks pass."
    )
    return build_continuation_task(db, job, follow_up)


def auto_fix_job(db: Session, job_id: str) -> Job:
    source = _get_job_or_404(db, job_id)
    if source.status != JobStatus.FAILED:
        raise HTTPException(
            status_code=409,
            detail=f"Auto-fix only available for failed jobs (status={source.status.value})",
        )
    if not can_auto_fix_job(source):
        raise HTTPException(
            status_code=409,
            detail="No test/check failures detected in logs — use Continue or Restart instead",
        )

    add_system_message(db, source.job_id, "Auto-fix queued from dashboard.")

    new_uuid = str(uuid.uuid4())
    composed_task = build_auto_fix_task(db, source)
    job = Job(
        job_id=new_uuid,
        project_id=source.project_id,
        task=composed_task,
        level=source.level,
        preset=_job_preset_value(source.preset),
        model=_job_model_value(source),
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
            content="Esegui fix — auto-generated from last test failures.",
        )
    )
    add_system_message(
        db,
        new_uuid,
        f"Auto-fix continuing from run {source.job_id[:8]}…",
    )
    db.commit()
    db.refresh(job)
    return job


def restart_job(db: Session, job_id: str) -> Job:
    source = _get_job_or_404(db, job_id)
    new_uuid = str(uuid.uuid4())
    job = Job(
        job_id=new_uuid,
        project_id=source.project_id,
        task=source.task,
        level=source.level,
        preset=_job_preset_value(source.preset),
        model=_job_model_value(source),
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
        preset=_job_preset_value(source.preset),
        model=_job_model_value(source),
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
