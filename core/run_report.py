"""Run summary artifact generation."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.logging_config import get_correlation_id
from core.models import OrchestrationResult, TaskRequest

logger = logging.getLogger(__name__)

DEFAULT_REPORT_DIR = Path.home() / ".hyper-orchestrator" / "reports"


def build_run_report(
    request: TaskRequest,
    result: OrchestrationResult,
    *,
    framework: str = "unknown",
    correlation_id: str | None = None,
    health_warnings: list[str] | None = None,
    dry_run: bool = False,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a JSON-serializable run summary."""
    report: dict[str, Any] = {
        "correlation_id": correlation_id or get_correlation_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "request": {
            "repo_url": request.repo_url,
            "task": request.task,
            "level": request.level.name,
            "preset": request.preset.value,
            "model": request.model,
            "max_debug_retries": request.max_debug_retries,
        },
        "result": {
            "success": result.success,
            "message": result.message,
            "level": result.level.name,
            "tasks_completed": result.tasks_completed,
            "pushed_to_staging": result.pushed_to_staging,
            "tests_passed": result.tests_passed,
            "tests_skipped": result.tests_skipped,
        },
        "framework": framework,
        "health_warnings": health_warnings or [],
    }
    if extra:
        report["details"] = extra
    return report


def write_run_report(report: dict[str, Any], report_dir: Path | None = None) -> Path:
    """Write run report JSON to disk."""
    directory = report_dir or DEFAULT_REPORT_DIR
    directory.mkdir(parents=True, exist_ok=True)
    cid = report.get("correlation_id", "unknown")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"run-{ts}-{cid}.json"
    path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Run report written to %s", path)
    return path
