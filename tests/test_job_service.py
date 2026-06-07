"""Tests for job lifecycle actions."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from server.database import Base
from server.job_service import cancel_job, continue_job, get_job_messages, requeue_job, restart_job
from server.models import Job, JobStatus, Project


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
