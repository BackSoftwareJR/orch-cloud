"""Hyper-orchestrator CLI subprocess execution."""

from __future__ import annotations

import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from core.models import AgentPreset
from core.presets.registry import resolve_model
from server.config import JOBS_DIR, PROJECT_ROOT, get_max_debug_retries

logger = logging.getLogger(__name__)


def _preset_cli_value(preset: str | AgentPreset) -> str:
    """Normalize preset for CLI ``--preset`` (always lowercase value string)."""
    if isinstance(preset, AgentPreset):
        return preset.value
    return AgentPreset.from_value(preset).value


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


def build_command(
    repo_url: str,
    task: str,
    level: str,
    preset: str | AgentPreset = "general",
    *,
    model: str | None = None,
    max_retries: int | None = None,
) -> list[str]:
    retries = max_retries if max_retries is not None else get_max_debug_retries()
    resolved_model = resolve_model(preset, model)
    return resolve_orchestrator_cmd() + [
        "--repo",
        repo_url,
        "--task",
        task,
        "--level",
        level,
        "--preset",
        _preset_cli_value(preset),
        "--model",
        resolved_model,
        "--max-retries",
        str(retries),
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
