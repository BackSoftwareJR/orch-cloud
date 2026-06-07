"""Tests for job lifecycle actions."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from core.exceptions import SecurityError
from core.models import TaskRequest
from server.database import Base
from server.job_service import (
    auto_fix_job,
    build_continuation_task,
    can_auto_fix_job,
    cancel_job,
    continue_job,
    extract_test_errors_from_log,
    get_job_messages,
    requeue_job,
    restart_job,
)
from server.models import Job, JobMessage, JobStatus, MessageRole, Project


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_project_and_job(db: Session, *, status: JobStatus = JobStatus.FAILED) -> Job:
    project = Project(name="Demo", repo_url="https://github.com/org/demo.git")
    db.add(project)
    db.commit()
    db.refresh(project)

    job = Job(
        job_id="job-001",
        project_id=project.id,
        task="Fix login bug",
        level="medium",
        status=status,
        thread_root_id="job-001",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def test_restart_job_creates_new_queued_run() -> None:
    db = _session()
    source = _seed_project_and_job(db)
    restarted = restart_job(db, source.job_id)
    assert restarted.job_id != source.job_id
    assert restarted.status == JobStatus.QUEUED
    assert restarted.parent_job_id == source.job_id


def test_restart_continue_auto_fix_normalize_legacy_preset_repr() -> None:
    db = _session()
    source = _seed_project_and_job(db, status=JobStatus.FAILED)
    source.preset = "AgentPreset.UX"
    source.error_message = "Process exited with code 1"
    db.commit()

    restarted = restart_job(db, source.job_id)
    assert restarted.preset == "ux"

    continued = continue_job(db, source.job_id, "Polish spacing on mobile")
    assert continued.preset == "ux"

    fixed = auto_fix_job(db, source.job_id)
    assert fixed.preset == "ux"


def test_requeue_job_resets_terminal_state() -> None:
    db = _session()
    job = _seed_project_and_job(db, status=JobStatus.FAILED)
    job.error_message = "boom"
    db.commit()
    requeued = requeue_job(db, job.job_id)
    assert requeued.status == JobStatus.QUEUED
    assert requeued.error_message is None


def test_cancel_job_marks_queued_as_cancelled() -> None:
    db = _session()
    job = _seed_project_and_job(db, status=JobStatus.QUEUED)
    cancelled = cancel_job(db, job.job_id)
    assert cancelled.status == JobStatus.CANCELLED


def test_continue_job_creates_follow_up_with_messages() -> None:
    db = _session()
    source = _seed_project_and_job(db, status=JobStatus.FAILED)
    continued = continue_job(db, source.job_id, "Also add tests for auth middleware")
    assert continued.job_id != source.job_id
    assert continued.parent_job_id == source.job_id
    messages = get_job_messages(db, continued.job_id)
    assert any(message.content == "Also add tests for auth middleware" for message in messages)


def test_can_auto_fix_for_failed_job_with_test_errors() -> None:
    db = _session()
    job = _seed_project_and_job(db, status=JobStatus.FAILED)
    job.error_message = "Medium task failed after 6 attempts"
    db.commit()

    from server.orchestrator import job_log_path

    log_path = job_log_path(job.job_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Validation failed:\nCommand: npm run test\nFAIL tests/auth.test.ts\n")
    assert can_auto_fix_job(job) is True


def test_auto_fix_job_creates_continuation() -> None:
    db = _session()
    source = _seed_project_and_job(db, status=JobStatus.FAILED)
    source.error_message = "Process exited with code 1"
    db.commit()

    fixed = auto_fix_job(db, source.job_id)
    assert fixed.job_id != source.job_id
    assert fixed.status == JobStatus.QUEUED
    assert fixed.parent_job_id == source.job_id
    assert "Auto-fix" in fixed.task or "auto-fix" in fixed.task.lower()


def test_build_continuation_task_stays_under_limit_with_long_history() -> None:
    db = _session()
    job = _seed_project_and_job(db, status=JobStatus.FAILED)
    job.task = "Fix authentication " + ("a" * 4000)
    db.commit()

    for index in range(50):
        db.add(
            JobMessage(
                job_id=job.job_id,
                role=MessageRole.USER if index % 2 == 0 else MessageRole.SYSTEM,
                content=f"Message {index}: " + ("x" * 600),
            )
        )
    db.commit()

    follow_up = "Please fix the remaining issues " + ("y" * 3000)
    task = build_continuation_task(db, job, follow_up)

    assert len(task) <= 8000
    TaskRequest(repo_url="https://github.com/org/demo.git", task=task)


def test_auto_fix_task_passes_cli_validation_with_large_log() -> None:
    db = _session()
    source = _seed_project_and_job(db, status=JobStatus.FAILED)
    source.error_message = "Medium task failed after 6 attempts"
    db.commit()

    from server.orchestrator import job_log_path

    log_path = job_log_path(source.job_id)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "Validation failed:\n"
        + "\n".join(f"FAIL test_case_{index}: assertion error" for index in range(500))
        + "\n"
    )

    fixed = auto_fix_job(db, source.job_id)
    assert len(fixed.task) <= 8000
    TaskRequest(repo_url="https://github.com/org/demo.git", task=fixed.task)


def test_extract_test_errors_from_log_caps_output() -> None:
    log_text = "Validation failed:\n" + "\n".join(
        f"error: line {index}" for index in range(500)
    )
    excerpt = extract_test_errors_from_log(log_text)
    assert len(excerpt) <= 2000
    assert "error:" in excerpt


def test_continue_job_rejects_oversized_follow_up() -> None:
    db = _session()
    source = _seed_project_and_job(db, status=JobStatus.FAILED)
    with pytest.raises(SecurityError):
        continue_job(db, source.job_id, "z" * 9000)
