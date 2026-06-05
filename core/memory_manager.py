"""Self-learning memory via SQLite for error/solution patterns."""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.exceptions import ProjectNotInitializedError
from core.models import LearnedPattern

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path.home() / ".hyper-orchestrator" / "learning_history.db"
DEFAULT_STALE_DAYS = 90
GLOBAL_PROJECT_KEY = "__global__"


class MemoryManager:
    """Persists and retrieves learned patterns from past orchestration runs."""

    def __init__(
        self,
        db_path: Path | None = None,
        *,
        stale_days: int = DEFAULT_STALE_DAYS,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self.stale_days = stale_days
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_key TEXT NOT NULL,
                    error_pattern TEXT NOT NULL,
                    solution_pattern TEXT NOT NULL,
                    task_summary TEXT DEFAULT '',
                    failure_count INTEGER DEFAULT 0,
                    is_global INTEGER DEFAULT 0,
                    pattern_hash TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS task_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_key TEXT NOT NULL,
                    task_summary TEXT NOT NULL,
                    error_signature TEXT,
                    success INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_project ON learning_history(project_key)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_patterns_hash ON learning_history(pattern_hash)"
            )
            conn.commit()
        self._purge_stale_patterns()

    @staticmethod
    def project_key_from_path(project_root: Path) -> str:
        return str(project_root.resolve())

    @staticmethod
    def _pattern_hash(error_pattern: str, solution_pattern: str) -> str:
        content = f"{error_pattern.strip()}|{solution_pattern.strip()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _purge_stale_patterns(self) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.stale_days)).isoformat()
        with self._connect() as conn:
            deleted = conn.execute(
                "DELETE FROM learning_history WHERE created_at < ?",
                (cutoff,),
            ).rowcount
            conn.commit()
        if deleted:
            logger.info("Purged %d stale patterns older than %d days", deleted, self.stale_days)

    def get_patterns(
        self,
        project_key: str,
        *,
        task: str = "",
        limit: int = 20,
        include_global: bool = True,
    ) -> list[LearnedPattern]:
        """Retrieve patterns ranked by relevance to the current task."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, project_key, error_pattern, solution_pattern,
                       task_summary, failure_count, is_global, created_at
                FROM learning_history
                WHERE project_key = ? OR (? = 1 AND is_global = 1)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_key, 1 if include_global else 0, limit * 3),
            ).fetchall()

        patterns: list[LearnedPattern] = []
        seen_hashes: set[str] = set()
        for row in rows:
            phash = self._pattern_hash(row["error_pattern"], row["solution_pattern"])
            if phash in seen_hashes:
                continue
            seen_hashes.add(phash)
            score = self._relevance_score(task, row["task_summary"], row["error_pattern"])
            patterns.append(
                LearnedPattern(
                    id=row["id"],
                    project_key=row["project_key"],
                    error_pattern=row["error_pattern"],
                    solution_pattern=row["solution_pattern"],
                    task_summary=row["task_summary"] or "",
                    failure_count=row["failure_count"] or 0,
                    is_global=bool(row["is_global"]),
                    relevance_score=score,
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            )

        patterns.sort(key=lambda p: p.relevance_score, reverse=True)
        return patterns[:limit]

    @staticmethod
    def _relevance_score(task: str, pattern_task: str, error_pattern: str) -> float:
        if not task.strip():
            return 0.5
        task_tokens = set(task.lower().split())
        score = 0.0
        for source in (pattern_task, error_pattern):
            source_tokens = set(source.lower().split())
            overlap = task_tokens & source_tokens
            if overlap:
                score += len(overlap) / max(len(task_tokens), 1)
        return min(score, 1.0)

    def record_attempt(
        self,
        project_key: str,
        task_summary: str,
        error_signature: str | None,
        success: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO task_attempts (project_key, task_summary, error_signature, success, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    project_key,
                    task_summary,
                    error_signature,
                    1 if success else 0,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def record_success_after_failures(
        self,
        project_key: str,
        task_summary: str,
        error_pattern: str,
        solution_pattern: str,
        failure_count: int,
        *,
        promote_global: bool = False,
    ) -> LearnedPattern:
        """Log a learned pattern when a task failed multiple times then succeeded."""
        phash = self._pattern_hash(error_pattern, solution_pattern)

        with self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM learning_history WHERE pattern_hash = ? AND project_key = ?",
                (phash, project_key),
            ).fetchone()
            if existing:
                logger.info("Skipping duplicate pattern for %s", project_key)
                return LearnedPattern(
                    id=existing["id"],
                    project_key=project_key,
                    error_pattern=error_pattern,
                    solution_pattern=solution_pattern,
                    task_summary=task_summary,
                    failure_count=failure_count,
                )

            pattern = LearnedPattern(
                project_key=project_key,
                error_pattern=error_pattern,
                solution_pattern=solution_pattern,
                task_summary=task_summary,
                failure_count=failure_count,
                is_global=promote_global or failure_count >= 3,
            )
            cursor = conn.execute(
                """
                INSERT INTO learning_history
                    (project_key, error_pattern, solution_pattern, task_summary,
                     failure_count, is_global, pattern_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pattern.project_key,
                    pattern.error_pattern,
                    pattern.solution_pattern,
                    pattern.task_summary,
                    pattern.failure_count,
                    1 if pattern.is_global else 0,
                    phash,
                    pattern.created_at.isoformat(),
                ),
            )
            if pattern.is_global:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO learning_history
                        (project_key, error_pattern, solution_pattern, task_summary,
                         failure_count, is_global, pattern_hash, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        GLOBAL_PROJECT_KEY,
                        pattern.error_pattern,
                        pattern.solution_pattern,
                        pattern.task_summary,
                        pattern.failure_count,
                        phash,
                        pattern.created_at.isoformat(),
                    ),
                )
            conn.commit()
            pattern.id = cursor.lastrowid

        logger.info(
            "Recorded learned pattern for %s (failures=%d, global=%s)",
            project_key,
            failure_count,
            pattern.is_global,
        )
        return pattern

    def get_recent_failure_signatures(
        self,
        project_key: str,
        task_summary: str,
        limit: int = 10,
    ) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT error_signature FROM task_attempts
                WHERE project_key = ? AND task_summary = ? AND success = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_key, task_summary, limit),
            ).fetchall()
        return [row["error_signature"] for row in rows if row["error_signature"]]

    def count_recent_failures(self, project_key: str, task_summary: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS cnt FROM task_attempts
                WHERE project_key = ? AND task_summary = ? AND success = 0
                AND created_at >= datetime('now', '-7 days')
                """,
                (project_key, task_summary),
            ).fetchone()
        return int(row["cnt"]) if row else 0

    def inject_into_cursorrules(
        self,
        project_root: Path,
        patterns: list[LearnedPattern],
        *,
        task: str = "",
    ) -> Path:
        """Append learned patterns to .cursorrules with structured sections."""
        if not project_root.exists() or not project_root.is_dir():
            raise ProjectNotInitializedError(
                f"Cannot inject patterns — project directory missing: {project_root}",
                remediation="Clone the repository before modifying .cursorrules.",
            )
        cursorrules_path = project_root / ".cursorrules"
        existing = ""
        if cursorrules_path.is_file():
            existing = cursorrules_path.read_text(encoding="utf-8", errors="replace")

        marker = "<!-- hyper-orchestrator-learned-patterns -->"
        if marker in existing:
            existing = existing.split(marker)[0].rstrip()

        if not patterns:
            return cursorrules_path

        project_patterns = [p for p in patterns if not p.is_global]
        global_patterns = [p for p in patterns if p.is_global]

        lines = [
            "",
            marker,
            "",
            "# HyperOrchestrator Learned Patterns",
            "",
            "<!-- DO NOT EDIT BELOW — managed by HyperOrchestrator -->",
            "",
        ]
        if task:
            lines.extend([f"**Current task context:** {task[:200]}", ""])

        if project_patterns:
            lines.extend(["## Project-Specific Patterns", ""])
            lines.extend(self._format_pattern_block(project_patterns))

        if global_patterns:
            lines.extend(["## Global Patterns (cross-project)", ""])
            lines.extend(self._format_pattern_block(global_patterns))

        content = existing + "\n".join(lines) + "\n"
        cursorrules_path.write_text(content, encoding="utf-8")
        logger.info("Injected %d learned patterns into %s", len(patterns), cursorrules_path)
        return cursorrules_path

    @staticmethod
    def _format_pattern_block(patterns: list[LearnedPattern]) -> list[str]:
        lines: list[str] = []
        for idx, pattern in enumerate(patterns, start=1):
            relevance = f" (relevance: {pattern.relevance_score:.0%})" if pattern.relevance_score else ""
            lines.extend(
                [
                    f"### Pattern {idx}{relevance}",
                    "",
                    "**When you see:**",
                    "```",
                    pattern.error_pattern[:1500],
                    "```",
                    "",
                    "**Try this approach:**",
                    "```",
                    pattern.solution_pattern[:1500],
                    "```",
                    "",
                    f"_From task: {pattern.task_summary or 'N/A'} | Failures before success: {pattern.failure_count}_",
                    "",
                ]
            )
        return lines

    def export_to_json(self, output_path: Path) -> None:
        """Export learning history to JSON for inspection."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, project_key, error_pattern, solution_pattern,
                       task_summary, failure_count, is_global, created_at
                FROM learning_history
                ORDER BY created_at DESC
                """
            ).fetchall()

        data = [dict(row) for row in rows]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
