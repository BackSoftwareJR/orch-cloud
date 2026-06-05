"""Hyper-orchestrator CLI subprocess execution."""

from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from server.config import JOBS_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)


def resolve_orchestrator_cmd() -> list[str]:
    """Return command prefix for hyper-orchestrator CLI."""
    venv_bin = PROJECT_ROOT / ".venv" / "bin" / "hyper-orchestrator"
    if venv_bin.is_file():
        return [str(venv_bin)]
    if shutil.which("hyper-orchestrator"):
        return ["hyper-orchestrator"]
    return [sys.executable, "-m", "core.main"]


def job_log_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.log"


def build_command(repo_url: str, task: str, level: str) -> list[str]:
    return resolve_orchestrator_cmd() + [
        "--repo",
        repo_url,
        "--task",
        task,
        "--level",
        level,
        "--json-log",
    ]


def write_log_header(log_path: Path, cmd: list[str], started_at: datetime) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"Command: {' '.join(cmd)}\n")
        log_file.write(f"Started: {started_at.isoformat()}\n\n")


def read_log_tail(log_path: Path, max_lines: int = 50) -> str | None:
    if not log_path.is_file():
        return None
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    return "\n".join(lines[-max_lines:]) if lines else ""
