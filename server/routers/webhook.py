"""Webhook trigger endpoint (backward compatible)."""

from __future__ import annotations

import uuid
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.presets.registry import resolve_level, resolve_model
from server.auth import verify_token
from server.database import get_db
from server.models import Job, JobStatus, Project
from server.orchestrator import job_log_path
from server.schemas import TriggerTaskRequest, TriggerTaskResponse

router = APIRouter(prefix="/webhook", tags=["webhook"])


def _repo_name_from_url(repo_url: str) -> str:
    path = urlparse(repo_url).path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    name = path.rsplit("/", 1)[-1] if path else "project"
    return name or "project"


def _get_or_create_project(db: Session, payload: TriggerTaskRequest) -> Project:
    if payload.project_id is not None:
        project = db.query(Project).filter(Project.id == payload.project_id).one_or_none()
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return project

    project = db.query(Project).filter(Project.repo_url == payload.repo_url).one_or_none()
    if project is not None:
        return project

    project = Project(
        name=_repo_name_from_url(payload.repo_url),
        repo_url=payload.repo_url,
        settings={},
    )
    db.add(project)
    db.flush()
    return project


@router.post("/trigger-task", response_model=TriggerTaskResponse)
def trigger_task(
    request: TriggerTaskRequest,
    db: Session = Depends(get_db),
    _: Annotated[None, Depends(verify_token)] = None,
) -> TriggerTaskResponse:
    project = _get_or_create_project(db, request)

    preset = request.preset
    level = resolve_level(preset, request.level).name.lower()
    model = resolve_model(preset, request.model)

    job_uuid = str(uuid.uuid4())
    job = Job(
        job_id=job_uuid,
        project_id=project.id,
        task=request.task,
        level=level,
        preset=preset,
        model=model,
        status=JobStatus.QUEUED,
        logs_path=str(job_log_path(job_uuid)),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return TriggerTaskResponse(
        job_id=job.job_id,
        status="queued",
        project_id=project.id,
    )
