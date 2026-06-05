"""CLI entrypoint for HyperOrchestrator."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from core.logging_config import configure_logging, new_correlation_id
from core.models import TaskLevel, TaskRequest
from core.orchestrator import HyperOrchestrator

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hyper-orchestrator",
        description="Self-improving multi-agent orchestration for code tasks",
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="Git repository URL to clone and modify",
    )
    parser.add_argument(
        "--task",
        required=True,
        help="Natural-language description of the task",
    )
    parser.add_argument(
        "--level",
        default="medium",
        help="Execution level: 1/fast, 2/medium, 3/pro (aliases: level1, l1, etc.)",
    )
    parser.add_argument(
        "--work-dir",
        default=None,
        help="Local directory for repository clone (default: .hyper-orchestrator/repos/<name>)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max debug retries for medium level (default: 3)",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o-mini",
        help="OpenAI model for PRO-level task decomposition",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config, run health checks and analysis without executing agents",
    )
    parser.add_argument(
        "--json-log",
        action="store_true",
        help="Emit structured JSON logs with correlation IDs",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Directory for run summary JSON (default: ~/.hyper-orchestrator/reports/)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> TaskRequest:
    parser = build_parser()
    args = parser.parse_args(argv)
    correlation_id = new_correlation_id()
    configure_logging(verbose=args.verbose, json_logs=args.json_log)

    try:
        level = TaskLevel.from_value(args.level)
    except ValueError as exc:
        parser.error(str(exc))

    return TaskRequest(
        repo_url=args.repo,
        task=args.task,
        level=level,
        work_dir=args.work_dir,
        max_debug_retries=args.max_retries,
        openai_model=args.openai_model,
        dry_run=args.dry_run,
        json_logs=args.json_log,
        report_dir=args.report_dir,
    )


def main(argv: list[str] | None = None) -> int:
    try:
        request = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1

    logger.info(
        "Starting HyperOrchestrator — level=%s repo=%s dry_run=%s",
        request.level.name,
        request.repo_url,
        request.dry_run,
    )

    orchestrator = HyperOrchestrator(request)
    result = orchestrator.run()

    status = "SUCCESS" if result.success else "FAILED"
    print(f"\n[{status}] {result.message}")
    print(f"  Level:          {result.level.name}")
    print(f"  Tasks done:     {result.tasks_completed}")
    print(f"  Pushed staging: {result.pushed_to_staging}")
    if result.tests_passed is not None:
        print(f"  Tests passed:   {result.tests_passed}")
    if result.correlation_id:
        print(f"  Correlation ID: {result.correlation_id}")
    if result.report_path:
        print(f"  Run report:     {result.report_path}")

    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
