"""Main HyperOrchestrator class — routes tasks across execution levels."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

from core.analyzers.detector import detect_framework, select_analyzer
from core.context_builder import prioritize_context
from core.docker_controller import DockerController
from core.exceptions import GitConflictError, GitError, HealthCheckError, HyperOrchestratorError, ProjectNotInitializedError
from core.github_manager import GitHubManager
from core.health import run_preflight_checks
from core.logging_config import get_correlation_id
from core.memory_manager import MemoryManager
from core.models import (
    AnalysisResult,
    AtomicTask,
    OrchestrationResult,
    TaskLevel,
    TaskPlan,
    TaskRequest,
)
from core.run_report import build_run_report, write_run_report
from core.task_planner import rollback_completed_steps, validate_and_order_plan

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
        strict: bool = False,
        context_suffix: str = "",
        prior_errors: str = "",
    ) -> str:
        assert self.project_root is not None and self.analysis is not None
        context_excerpt = prioritize_context(
            self.analysis.summary, max_chars=6000, task=self.request.task
        )
        lines = [
            f"You are working in a {self.framework} project at /workspace.",
            f"Project context (prioritized excerpt):\n{context_excerpt}",
            "",
            f"Task: {task}",
        ]
        if strict:
            lines.extend(
                [
                    "",
                    "MODE: FAST — Apply the minimal fix only.",
                    "- Do not run tests.",
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
        return "\n".join(lines)

    def _run_fast(self) -> OrchestrationResult:
        assert self.project_root is not None and self._git is not None
        prompt = self._build_agent_prompt(self.request.task, strict=True)

        result = self.docker.run_agent(
            self.project_root,
            prompt,
            model="composer-2.5",
            yolo=False,
        )

        if not result.success:
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

    def _run_medium(self) -> OrchestrationResult:
        assert self.project_root is not None and self._git is not None
        project_key = MemoryManager.project_key_from_path(self.project_root)
        prior_errors = ""
        failure_count = 0

        for attempt in range(1, self.request.max_debug_retries + 1):
            logger.info(
                "Medium attempt %d/%d",
                attempt,
                self.request.max_debug_retries,
            )
            prompt = self._build_agent_prompt(
                self.request.task,
                prior_errors=prior_errors,
            )
            agent_result = self.docker.run_agent(
                self.project_root,
                prompt,
                model="composer-2.5",
                yolo=True,
            )

            if not agent_result.success:
                prior_errors = DockerController.extract_error_signature(agent_result.logs)
                failure_count += 1
                self.memory.record_attempt(
                    project_key,
                    self.request.task,
                    prior_errors,
                    success=False,
                )
                continue

            test_result = self.docker.run_command(
                self.project_root,
                self.test_command or "npm run test",
            )
            if test_result.success:
                if failure_count > 0:
                    self.memory.record_success_after_failures(
                        project_key,
                        self.request.task,
                        error_pattern=prior_errors or "Unknown test/agent failure",
                        solution_pattern=f"Resolved after {failure_count} failed attempt(s)",
                        failure_count=failure_count,
                    )
                self.memory.record_attempt(project_key, self.request.task, None, success=True)

                committed = self._git.stage_all_and_commit(
                    f"hyper-orchestrator: {self.request.task[:72]}"
                )
                pushed = False
                if committed:
                    self._git.push_staging()
                    pushed = True

                return OrchestrationResult(
                    success=True,
                    level=TaskLevel.MEDIUM,
                    message="Medium task completed with passing tests",
                    pushed_to_staging=pushed,
                    tasks_completed=1,
                    tests_passed=True,
                )

            prior_errors = DockerController.extract_error_signature(test_result.logs)
            failure_count += 1
            self.memory.record_attempt(
                project_key,
                self.request.task,
                prior_errors,
                success=False,
            )
            fix_prompt = self._build_agent_prompt(
                self.request.task,
                prior_errors=f"Tests failed:\n{prior_errors}",
                context_suffix="Fix the failing tests before finishing.",
            )
            self.docker.run_agent(
                self.project_root,
                fix_prompt,
                model="composer-2.5",
                yolo=True,
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
            prompt = self._build_agent_prompt(
                f"{atomic.title}\n\n{atomic.description}",
                context_suffix=(
                    f"This is step {atomic.id} of {len(plan.tasks)} in a larger plan.\n"
                    f"Plan summary: {plan.summary}"
                ),
            )
            result = self.docker.run_agent(
                self.project_root,
                prompt,
                model="composer-2.5",
                yolo=True,
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
        fix_prompt = self._build_agent_prompt(
            atomic.description,
            prior_errors=f"Validation failed:\n{error_sig}",
        )
        fix_result = self.docker.run_agent(
            self.project_root,
            fix_prompt,
            model="composer-2.5",
            yolo=True,
        )
        if not fix_result.success:
            return False

        retry = self.docker.run_command(self.project_root, atomic.validation_command)
        if not retry.success:
            self.memory.record_attempt(project_key, atomic.title, error_sig, success=False)
        return retry.success

    def _decompose_task(self) -> TaskPlan:
        assert self.project_root is not None and self.analysis is not None
        context = prioritize_context(
            self.analysis.summary, max_chars=6000, task=self.request.task
        )
        system_prompt = (
            "You are a senior software architect. Break the user's task into atomic, "
            "sequential steps for an AI coding agent. Return ONLY valid JSON matching:\n"
            '{"summary": "...", "tasks": [{"id": 1, "title": "...", "description": "...", '
            '"validation_command": "optional shell command or null", "depends_on": [optional int ids]}]}\n'
            f"Framework: {self.framework}. Test command: {self.test_command}."
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
