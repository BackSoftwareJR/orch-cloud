"""Job management endpoints."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.presets.registry import resolve_level
from server.auth import verify_token
from server.deps import optional_verify_token
from server.database import get_db
from server.job_service import (
    auto_fix_job,
    cancel_job,
    can_auto_fix_job,
    continue_job,
    get_job_messages,
    requeue_job,
    restart_job,
    seed_task_message,
)
from server.models import Job, JobStatus, Project
from server.orchestrator import job_log_path, read_log_tail
from server.schemas import (
    JobContinueRequest,
    JobCreate,
    JobMessageResponse,
    JobResponse,
    JobStatusResponse,
)

router = APIRouter(tags=["jobs"])


def _job_to_response(job: Job, *, include_tail: bool = False) -> JobResponse:
    tail: str | None = None
    if include_tail:
        path = Path(job.logs_path) if job.logs_path else job_log_path(job.job_id)
        tail = read_log_tail(path)

    return JobResponse(
        job_id=job.job_id,
        project_id=job.project_id,
        status=job.status,
        level=job.level,
        preset=job.preset,
        task=job.task,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        logs_path=job.logs_path,
        error_message=job.error_message,
        parent_job_id=job.parent_job_id,
        thread_root_id=job.thread_root_id,
        log_tail=tail,
        can_auto_fix=can_auto_fix_job(job),
    )


def _exit_code_from_status(status: JobStatus) -> int | None:
    if status == JobStatus.COMPLETED:
        return 0
    if status == JobStatus.FAILED:
        return 1
    return None


@router.get("/jobs", response_model=list[JobResponse])
def list_jobs(
    db: Session = Depends(get_db),
    project_id: Annotated[int | None, Query()] = None,
    status: Annotated[JobStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[JobResponse]:
    query = db.query(Job).order_by(Job.created_at.desc())
    if project_id is not None:
        query = query.filter(Job.project_id == project_id)
    if status is not None:
        query = query.filter(Job.status == status)
    jobs = query.limit(limit).all()
    return [_job_to_response(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    db: Session = Depends(get_db),
    tail: Annotated[bool, Query()] = True,
) -> JobResponse:
    job = db.query(Job).filter(Job.job_id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_response(job, include_tail=tail)


@router.get("/jobs/{job_id}/messages", response_model=list[JobMessageResponse])
def list_job_messages(job_id: str, db: Session = Depends(get_db)) -> list[JobMessageResponse]:
    messages = get_job_messages(db, job_id)
    return [
        JobMessageResponse(
            id=message.id,
            job_id=message.job_id,
            role=message.role.value,
            content=message.content,
            created_at=message.created_at,
        )
        for message in messages
    ]


@router.post("/jobs/{job_id}/restart", response_model=JobResponse, status_code=201)
def restart_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = restart_job(db, job_id)
    return _job_to_response(job)


@router.post("/jobs/{job_id}/requeue", response_model=JobResponse)
def requeue_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = requeue_job(db, job_id)
    return _job_to_response(job)


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
def cancel_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = cancel_job(db, job_id)
    return _job_to_response(job)


@router.post("/jobs/{job_id}/continue", response_model=JobResponse, status_code=201)
def continue_job_endpoint(
    job_id: str,
    payload: JobContinueRequest,
    db: Session = Depends(get_db),
) -> JobResponse:
    job = continue_job(db, job_id, payload.message)
    return _job_to_response(job)


@router.post("/jobs/{job_id}/auto-fix", response_model=JobResponse, status_code=201)
def auto_fix_job_endpoint(job_id: str, db: Session = Depends(get_db)) -> JobResponse:
    job = auto_fix_job(db, job_id)
    return _job_to_response(job)


@router.get("/jobs/{job_id}/legacy", response_model=JobStatusResponse)
def get_job_status_legacy(
    job_id: str,
    _: Annotated[None, Depends(verify_token)],
    db: Session = Depends(get_db),
) -> JobStatusResponse:
    """Backward-compatible status endpoint for webhook clients."""
    job = db.query(Job).filter(Job.job_id == job_id).one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    log_path = job.logs_path or str(job_log_path(job.job_id))
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value.lower(),
        log_path=log_path,
        log_tail=read_log_tail(Path(log_path)),
        exit_code=_exit_code_from_status(job.status),
        created_at=job.created_at.isoformat() if job.created_at else None,
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
    )


@router.post("/projects/{project_id}/jobs", response_model=JobResponse, status_code=201)
def trigger_project_job(
    project_id: int,
    payload: JobCreate,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(optional_verify_token)] = None,
) -> JobResponse:
    project = db.query(Project).filter(Project.id == project_id).one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    preset = payload.preset
    level = resolve_level(preset, payload.level).name.lower()

    job_uuid = str(uuid.uuid4())
    job = Job(
        job_id=job_uuid,
        project_id=project.id,
        task=payload.task,
        level=level,
        preset=preset,
        status=JobStatus.QUEUED,
        logs_path=str(job_log_path(job_uuid)),
        thread_root_id=job_uuid,
    )
    db.add(job)
    db.flush()
    seed_task_message(db, job)
    db.commit()
    db.refresh(job)
    return _job_to_response(job)
