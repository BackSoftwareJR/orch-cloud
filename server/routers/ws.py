"""WebSocket log streaming endpoint."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from server.database import SessionLocal
from server.models import Job, JobStatus
from server.orchestrator import job_log_path

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

POLL_INTERVAL = 0.5
TERMINAL_STATUSES = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


async def _stream_log_tail(websocket: WebSocket, log_path: Path, stop_event: asyncio.Event) -> None:
    position = 0
    while not stop_event.is_set():
        if log_path.is_file():
            try:
                with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
                    log_file.seek(position)
                    chunk = log_file.read()
                    if chunk:
                        await websocket.send_text(chunk)
                        position = log_file.tell()
            except OSError as exc:
                logger.debug("Log read error for %s: %s", log_path, exc)
        await asyncio.sleep(POLL_INTERVAL)

    if log_path.is_file():
        try:
            with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
                log_file.seek(position)
                remainder = log_file.read()
                if remainder:
                    await websocket.send_text(remainder)
        except OSError:
            pass


async def _watch_job_status(job_id: str, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        session = SessionLocal()
        try:
            job = session.query(Job).filter(Job.job_id == job_id).one_or_none()
            if job is None or job.status in TERMINAL_STATUSES:
                stop_event.set()
                return
        finally:
            session.close()
        await asyncio.sleep(POLL_INTERVAL)


@router.websocket("/ws/logs/{job_id}")
async def stream_job_logs(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()

    session = SessionLocal()
    try:
        job = session.query(Job).filter(Job.job_id == job_id).one_or_none()
    finally:
        session.close()

    if job is None:
        await websocket.send_text(f"[system] Job {job_id} not found.\n")
        await websocket.close(code=4404)
        return

    log_path = Path(job.logs_path) if job.logs_path else job_log_path(job_id)
    stop_event = asyncio.Event()
    watcher = asyncio.create_task(_watch_job_status(job_id, stop_event))

    try:
        if not log_path.is_file():
            await websocket.send_text("[system] Waiting for log file...\n")
        await _stream_log_tail(websocket, log_path, stop_event)
        await websocket.send_text("\n[system] Log stream ended.\n")
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for job %s", job_id)
    finally:
        stop_event.set()
        watcher.cancel()
        try:
            await watcher
        except asyncio.CancelledError:
            pass
