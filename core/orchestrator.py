"""Main HyperOrchestrator class — routes tasks across execution levels."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from core.analyzers.detector import detect_framework, select_analyzer
from core.context_builder import build_agent_context
from core.presets.registry import PresetDefinition, get_preset, resolve_model
from core.docker_controller import DockerController
from core.exceptions import GitConflictError, GitError, HealthCheckError, HyperOrchestratorError, ProjectNotInitializedError
from core.github_manager import GitHubManager
from core.health import run_preflight_checks
from core.logging_config import get_correlation_id
from core.memory_manager import MemoryManager
from core.security import redact_secrets
from core.models import (
    AnalysisResult,
    AtomicTask,
    OrchestrationResult,
    TaskLevel,
    TaskPlan,
    TaskRequest,
)
from core.execution_router import ExecutionRouter
from core.run_report import build_run_report, write_run_report
from core.supervisor import summarize_run
from core.task_planner import rollback_completed_steps, validate_and_order_plan
from core.test_runner import TestCheckResult, format_test_failure_for_agent, run_preset_check

logger = logging.getLogger(__name__)

SYSTEM_CONTEXT_FILENAME = ".system_context.md"


class HyperOrchestrator:
    """Self-improving multi-agent orchestration system."""

    def __init__(
        self,
        request: TaskRequest,
        *,
        memory: MemoryManager | None = None,
        docker: DockerController | None = None,
        work_base_dir: Path | None = None,
    ) -> None:
        self.request = request
        self.memory = memory or MemoryManager()
        self.docker = docker or DockerController()
        self.work_base_dir = work_base_dir or Path.cwd() / ".hyper-orchestrator" / "repos"
        self.project_root: Path | None = None
        self.framework: str = "unknown"
        self.framework_confidence: float = 0.0
        self.analysis: AnalysisResult | None = None
        self.test_command: str | None = None
        self._git: GitHubManager | None = None
        self._openai_client: OpenAI | None = None
        self._health_warnings: list[str] = []
        self._completed_pro_steps: list[int] = []
        self.preset_def: PresetDefinition = get_preset(request.preset)
        self._execution_router = ExecutionRouter(docker=self.docker, json_logs=request.json_logs)
        self._checkpoints: list[dict[str, object]] = []
        self.agent_model = resolve_model(request.preset, request.model)

    @property
    def openai_client(self) -> OpenAI:
        if self._openai_client is None:
            import os

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "OPENAI_API_KEY is required for PRO-level task decomposition"
                )
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client

    def run(self) -> OrchestrationResult:
        """Execute the full orchestration workflow."""
        correlation_id = get_correlation_id()
        result: OrchestrationResult | None = None
        try:
            health = run_preflight_checks(
                repo_url=self.request.repo_url,
                docker=self.docker,
                require_openai=self.request.level == TaskLevel.PRO,
            )
            self._health_warnings = health.warnings
            if not self.request.dry_run:
                health.raise_if_failed()
            for warning in health.warnings:
                logger.warning(warning)

            logger.info(
                "Preset=%s model=%s yolo=%s",
                self.preset_def.id.value,
                self.agent_model,
                self.preset_def.yolo,
            )

            self._prepare_repository()
            self._analyze_project()
            self._inject_learned_patterns()

            if self.request.dry_run:
                result = self._dry_run_result()
            elif self.request.level == TaskLevel.FAST:
                result = self._run_fast()
            elif self.request.level == TaskLevel.MEDIUM:
                result = self._run_medium()
            else:
                result = self._run_pro()

            result.correlation_id = correlation_id
            report_path = self._write_report(result)
            result.report_path = report_path
            return result

        except GitConflictError as exc:
            logger.error("Git conflict: %s", exc)
            result = OrchestrationResult(
                success=False,
                level=self.request.level,
                message=str(exc),
                correlation_id=correlation_id,
            )
        except GitError as exc:
            logger.error("Git error: %s", exc)
            remediation = f" {exc.remediation}" if exc.remediation else ""
            result = OrchestrationResult(
                success=False,
                level=self.request.level,
                message=f"Git operation failed: {exc}{remediation}",
                correlation_id=correlation_id,
            )
        except HealthCheckError as exc:
            logger.error("Health check failed: %s", exc)
            result = OrchestrationResult(
                success=False,
                level=self.request.level,
                message=str(exc),
                correlation_id=correlation_id,
            )
        except (RuntimeError, HyperOrchestratorError) as exc:
            logger.error("Orchestration error: %s", exc)
            result = OrchestrationResult(
                success=False,
                level=self.request.level,
                message=str(exc),
                correlation_id=correlation_id,
            )
        finally:
            self.docker.close()

        if result is not None:
            result.report_path = self._write_report(result)
        return result or OrchestrationResult(
            success=False,
            level=self.request.level,
            message="Unknown orchestration failure",
            correlation_id=correlation_id,
        )

    def _write_report(self, result: OrchestrationResult) -> Path | None:
        report_dir = Path(self.request.report_dir) if self.request.report_dir else None
        report = build_run_report(
            self.request,
            result,
            framework=self.framework,
            health_warnings=self._health_warnings,
            dry_run=self.request.dry_run,
            extra={
                "framework_confidence": self.framework_confidence,
                "test_command": self.test_command,
                "tests_skipped": result.tests_skipped,
                "checkpoints": self._checkpoints,
            },
        )
        try:
            return write_run_report(report, report_dir)
        except OSError as exc:
            logger.warning("Could not write run report: %s", exc)
            return None

    def _dry_run_result(self) -> OrchestrationResult:
        plan_summary = ""
        if self.request.level == TaskLevel.PRO:
            plan = self._decompose_task()
            plan_summary = f" PRO plan: {len(plan.tasks)} steps — {plan.summary[:120]}"
        return OrchestrationResult(
            success=True,
            level=self.request.level,
            message=(
                f"Dry-run OK — framework={self.framework} "
                f"(confidence={self.framework_confidence:.0%}), "
                f"test_command={self.test_command}{plan_summary}"
            ),
            tasks_completed=0,
        )

    def _prepare_repository(self) -> None:
        if self.request.work_dir:
            work_dir = Path(self.request.work_dir)
        else:
            repo_name = GitHubManager.sanitize_repo_name(self.request.repo_url)
            work_dir = self.work_base_dir / repo_name

        git = GitHubManager(self.request.repo_url, work_dir)
        if not self.request.dry_run:
            self.project_root = git.clone_or_update()
            git.checkout_staging()
        else:
            self.project_root = work_dir
        self._git = git

    def _analyze_project(self) -> None:
        assert self.project_root is not None
        if not self.request.dry_run:
            if not self.project_root.exists():
                raise ProjectNotInitializedError(
                    f"Project directory does not exist: {self.project_root}",
                    remediation="Ensure clone_or_update() completed successfully before analysis.",
                )
            if not self.project_root.is_dir():
                raise ProjectNotInitializedError(
                    f"Project path is not a directory: {self.project_root}",
                    remediation="Verify work_dir points to the cloned repository root.",
                )

        detection = detect_framework(self.project_root)
        self.framework = detection.framework
        self.framework_confidence = detection.confidence

        analyzer = select_analyzer(self.project_root)
        self.analysis = analyzer.analyze()
        self.framework = self.analysis.framework
        self.test_command = str(self.analysis.details.get("test_command", "npm run test"))
        self._write_system_context()
        logger.info(
            "Detected framework: %s (confidence=%.0f%%)",
            self.framework,
            self.framework_confidence * 100,
        )

    def _write_system_context(self) -> None:
        assert self.project_root is not None and self.analysis is not None
        if not self.project_root.exists():
            raise ProjectNotInitializedError(
                f"Cannot write system context — project directory missing: {self.project_root}",
                remediation="Clone the repository before writing .system_context.md.",
            )
        header = (
            "# System Context\n\n"
            f"Generated by HyperOrchestrator at {datetime.now(timezone.utc).isoformat()}\n\n"
            f"**Framework:** {self.framework} (confidence: {self.framework_confidence:.0%})\n\n"
            f"**Task:** {self.request.task}\n\n"
            f"**Level:** {self.request.level.name}\n\n"
            f"**Preset:** {self.preset_def.id.value}\n\n"
        )
        content = header + self.analysis.summary
        path = self.project_root / SYSTEM_CONTEXT_FILENAME
        path.write_text(content, encoding="utf-8")
        logger.info("Wrote %s", path)

    def _inject_learned_patterns(self) -> None:
        assert self.project_root is not None
        if not self.project_root.exists() or not self.project_root.is_dir():
            raise ProjectNotInitializedError(
                f"Cannot inject patterns — project directory missing: {self.project_root}",
                remediation="Clone the repository before modifying .cursorrules.",
            )
        project_key = MemoryManager.project_key_from_path(self.project_root)
        patterns = self.memory.get_patterns(project_key, task=self.request.task)
        if patterns:
            self.memory.inject_into_cursorrules(
                self.project_root, patterns, task=self.request.task
            )

    def _build_agent_prompt(
        self,
        task: str,
        *,
        strict: bool | None = None,
        context_suffix: str = "",
        prior_errors: str = "",
    ) -> str:
        assert self.project_root is not None and self.analysis is not None
        preset = self.preset_def
        if strict is None:
            strict = preset.strict_by_default

        context_excerpt = build_agent_context(
            self.project_root,
            self.analysis.summary,
            task=self.request.task,
            preset=preset.id,
            section_priorities=preset.context_priorities or None,
        )
        lines = [
            preset.system_prompt,
            "",
            f"You are working in a {self.framework} project at /workspace.",
            context_excerpt,
            "",
            f"Task: {task}",
            "",
            preset.constraints_block,
        ]
        if strict:
            lines.extend(
                [
                    "",
                    "MODE: STRICT — Apply the minimal change required.",
                    "- Do not run tests unless the orchestrator runs them separately.",
                    "- Do not refactor unrelated code.",
                    "- Commit-ready changes only.",
                ]
            )
        if prior_errors:
            lines.extend(
                ["", "Previous attempt failed with:", prior_errors, "", "Fix the issue and retry."]
            )
        if context_suffix:
            lines.extend(["", context_suffix])
        lines.extend(["", preset.quality_block])
        return "\n".join(lines)

    def _record_agent_checkpoint(
        self,
        outcome,
        *,
        attempt: int | None = None,
    ) -> None:
        checkpoint = summarize_run(
            outcome.result,
            outcome.result.logs,
            model=outcome.model_used,
            attempt=attempt,
        )
        if outcome.model_switches:
            checkpoint["model_switches"] = outcome.model_switches
        self._checkpoints.append(checkpoint)

    def _run_preset_agent(
        self,
        task: str,
        *,
        strict: bool | None = None,
        context_suffix: str = "",
        prior_errors: str = "",
        attempt: int | None = None,
    ):
        assert self.project_root is not None
        preset = self.preset_def
        prompt = self._build_agent_prompt(
            task,
            strict=strict,
            context_suffix=context_suffix,
            prior_errors=prior_errors,
        )
        outcome = self._execution_router.run_agent(
            self.project_root,
            prompt,
            model=self.agent_model,
            yolo=preset.yolo,
        )
        self._record_agent_checkpoint(outcome, attempt=attempt)
        return outcome.result

    def _run_fast(self) -> OrchestrationResult:
        assert self.project_root is not None and self._git is not None
        result = self._run_preset_agent(self.request.task, strict=True)

        if not result.success:
            logger.error(
                "Fast agent failed (exit=%s):\n%s",
                result.exit_code,
                redact_secrets(result.logs[-6000:] or "(empty agent logs)"),
            )
            return OrchestrationResult(
                success=False,
                level=TaskLevel.FAST,
                message=f"Agent failed (exit {result.exit_code})",
            )

        committed = self._git.stage_all_and_commit(f"hyper-orchestrator: {self.request.task[:72]}")
        pushed = False
        if committed:
            self._git.push_staging()
            pushed = True

        return OrchestrationResult(
            success=True,
            level=TaskLevel.FAST,
            message="Fast task completed and pushed to staging",
            pushed_to_staging=pushed,
            tasks_completed=1,
        )

    def _should_push_on_test_failure(self) -> bool:
        env = os.environ.get("PUSH_ON_TEST_FAILURE", "").strip().lower()
        if env in ("1", "true", "yes"):
            return True
        if env in ("0", "false", "no"):
            return False
        return self.preset_def.push_on_test_failure

    def _log_test_check(self, attempt: int, check: TestCheckResult) -> None:
        summary = {
            "event": "test_check",
            "attempt": attempt,
            "strategy": check.strategy,
            "command": check.command,
            "success": check.success,
            "skipped": check.skipped,
            "warnings_only": check.warnings_only,
            "output_tail": redact_secrets(check.logs.strip()[-8000:]),
        }
        if self.request.json_logs:
            logger.info(json.dumps(summary, ensure_ascii=False))
        else:
            logger.info(
                "Test check attempt=%d strategy=%s command=%s success=%s",
                attempt,
                check.strategy,
                check.command,
                check.success,
            )

    def _commit_and_push(self, message: str) -> bool:
        assert self._git is not None
        committed = self._git.stage_all_and_commit(message)
        if committed:
            self._git.push_staging()
            return True
        return False

    def _run_medium(self) -> OrchestrationResult:
        assert self.project_root is not None and self._git is not None
        project_key = MemoryManager.project_key_from_path(self.project_root)
        prior_errors = ""
        failure_count = 0
        agent_succeeded = False
        last_check: TestCheckResult | None = None
        fallback_command = self.test_command or "npm run test"

        for attempt in range(1, self.request.max_debug_retries + 1):
            logger.info(
                "Medium attempt %d/%d",
                attempt,
                self.request.max_debug_retries,
            )
            agent_result = self._run_preset_agent(
                self.request.task,
                prior_errors=prior_errors,
                attempt=attempt,
            )

            if not agent_result.success:
                prior_errors = DockerController.extract_error_signature(agent_result.logs)
                logger.error(
                    "Agent attempt %d failed (exit=%s):\n%s",
                    attempt,
                    agent_result.exit_code,
                    redact_secrets(agent_result.logs[-6000:] or "(empty agent logs)"),
                )
                failure_count += 1
                self.memory.record_attempt(
                    project_key,
                    self.request.task,
                    prior_errors,
                    success=False,
                )
                continue

            agent_succeeded = True
            check = run_preset_check(
                self.docker,
                self.project_root,
                self.preset_def,
                fallback_command,
            )
            last_check = check
            self._log_test_check(attempt, check)

            if check.skipped or check.success or check.warnings_only:
                if failure_count > 0:
                    self.memory.record_success_after_failures(
                        project_key,
                        self.request.task,
                        error_pattern=prior_errors or "Unknown test/agent failure",
                        solution_pattern=f"Resolved after {failure_count} failed attempt(s)",
                        failure_count=failure_count,
                    )
                self.memory.record_attempt(project_key, self.request.task, None, success=True)

                pushed = self._commit_and_push(
                    f"hyper-orchestrator: {self.request.task[:72]}"
                )
                msg = "Medium task completed with passing checks"
                if check.warnings_only:
                    msg = "Medium task completed (lint warnings only — pushed)"
                elif check.skipped:
                    msg = "Medium task completed (checks skipped for preset)"

                return OrchestrationResult(
                    success=True,
                    level=TaskLevel.MEDIUM,
                    message=msg,
                    pushed_to_staging=pushed,
                    tasks_completed=1,
                    tests_passed=True if not check.skipped else None,
                )

            prior_errors = format_test_failure_for_agent(check)
            failure_count += 1
            self.memory.record_attempt(
                project_key,
                self.request.task,
                prior_errors,
                success=False,
            )
            logger.warning(
                "Checks failed on attempt %d/%d — launching fix agent",
                attempt,
                self.request.max_debug_retries,
            )
            self._run_preset_agent(
                self.request.task,
                prior_errors=f"Validation failed:\n\n{prior_errors}",
                context_suffix="Fix the failing checks before finishing.",
            )

        if (
            agent_succeeded
            and self._should_push_on_test_failure()
            and self._git.has_uncommitted_changes()
        ):
            pushed = self._commit_and_push(
                f"hyper-orchestrator (tests skipped): {self.request.task[:60]}"
            )
            detail = ""
            if last_check:
                detail = f" Last command: {last_check.command}."
            return OrchestrationResult(
                success=True,
                level=TaskLevel.MEDIUM,
                message=(
                    f"Pushed to staging with tests_skipped after "
                    f"{self.request.max_debug_retries} attempts.{detail}"
                ),
                pushed_to_staging=pushed,
                tasks_completed=1,
                tests_passed=False,
                tests_skipped=True,
            )

        return OrchestrationResult(
            success=False,
            level=TaskLevel.MEDIUM,
            message=f"Medium task failed after {self.request.max_debug_retries} attempts",
            tests_passed=False,
        )

    def _run_pro(self) -> OrchestrationResult:
        assert self.project_root is not None and self._git is not None
        plan = self._decompose_task()
        completed = 0
        project_key = MemoryManager.project_key_from_path(self.project_root)
        self._completed_pro_steps = []

        for atomic in plan.tasks:
            logger.info("PRO step %d: %s", atomic.id, atomic.title)
            result = self._run_preset_agent(
                f"{atomic.title}\n\n{atomic.description}",
                context_suffix=(
                    f"This is step {atomic.id} of {len(plan.tasks)} in a larger plan.\n"
                    f"Plan summary: {plan.summary}"
                ),
            )
            if not result.success:
                error_sig = DockerController.extract_error_signature(result.logs)
                self.memory.record_attempt(project_key, atomic.title, error_sig, success=False)
                rollback_completed_steps(self._git, self._completed_pro_steps)
                return OrchestrationResult(
                    success=False,
                    level=TaskLevel.PRO,
                    message=f"PRO task failed at step {atomic.id}: {atomic.title}",
                    tasks_completed=completed,
                )

            if atomic.validation_command:
                if not self._validate_step(atomic, project_key):
                    rollback_completed_steps(self._git, self._completed_pro_steps)
                    return OrchestrationResult(
                        success=False,
                        level=TaskLevel.PRO,
                        message=f"Validation failed at step {atomic.id}: {atomic.title}",
                        tasks_completed=completed,
                    )

            self.memory.record_attempt(project_key, atomic.title, None, success=True)
            self._completed_pro_steps.append(atomic.id)
            completed += 1

        if self.test_command:
            final_test = self.docker.run_command(self.project_root, self.test_command)
            if not final_test.success:
                rollback_completed_steps(self._git, self._completed_pro_steps)
                return OrchestrationResult(
                    success=False,
                    level=TaskLevel.PRO,
                    message="PRO plan completed but final test suite failed",
                    tasks_completed=completed,
                    tests_passed=False,
                )

        committed = self._git.stage_all_and_commit(
            f"hyper-orchestrator PRO: {self.request.task[:60]}"
        )
        pushed = False
        if committed:
            self._git.push_staging()
            pushed = True

        return OrchestrationResult(
            success=True,
            level=TaskLevel.PRO,
            message=f"PRO plan completed ({completed} steps)",
            pushed_to_staging=pushed,
            tasks_completed=completed,
            tests_passed=True if self.test_command else None,
        )

    def _validate_step(self, atomic: AtomicTask, project_key: str) -> bool:
        assert self.project_root is not None
        assert atomic.validation_command is not None

        validation = self.docker.run_command(
            self.project_root,
            atomic.validation_command,
        )
        if validation.success:
            return True

        error_sig = DockerController.extract_error_signature(validation.logs)
        fix_result = self._run_preset_agent(
            atomic.description,
            prior_errors=f"Validation failed:\n{error_sig}",
        )
        if not fix_result.success:
            return False

        retry = self.docker.run_command(self.project_root, atomic.validation_command)
        if not retry.success:
            self.memory.record_attempt(project_key, atomic.title, error_sig, success=False)
        return retry.success

    def _decompose_task(self) -> TaskPlan:
        assert self.project_root is not None and self.analysis is not None
        context = build_agent_context(
            self.project_root,
            self.analysis.summary,
            task=self.request.task,
            preset=self.preset_def.id,
            section_priorities=self.preset_def.context_priorities or None,
        )
        base_prompt = (
            "You are a senior software architect. Break the user's task into atomic, "
            "sequential steps for an AI coding agent. Return ONLY valid JSON matching:\n"
            '{"summary": "...", "tasks": [{"id": 1, "title": "...", "description": "...", '
            '"validation_command": "optional shell command or null", "depends_on": [optional int ids]}]}\n'
            f"Framework: {self.framework}. Test command: {self.test_command}."
        )
        system_prompt = self.preset_def.pro_decompose_prompt or base_prompt
        if self.preset_def.pro_decompose_prompt:
            system_prompt = (
                f"{self.preset_def.pro_decompose_prompt}\n\n"
                f"{base_prompt}"
            )
        user_content = f"Project context:\n{context}\n\nTask to decompose:\n{self.request.task}"

        response = self.openai_client.chat.completions.create(
            model=self.request.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        raw_tasks = data.get("tasks", [])
        if not raw_tasks:
            raw_tasks = [
                {
                    "id": 1,
                    "title": "Implement task",
                    "description": self.request.task,
                    "validation_command": self.test_command,
                }
            ]
        return validate_and_order_plan(raw_tasks, summary=data.get("summary", ""))
