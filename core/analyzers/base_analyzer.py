"""Abstract base class for project framework analyzers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from core.models import AnalysisResult, FrameworkType

logger = logging.getLogger(__name__)


class BaseAnalyzer(ABC):
    """Detects and analyzes a specific project framework."""

    framework: FrameworkType

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    @classmethod
    @abstractmethod
    def can_analyze(cls, project_root: Path) -> bool:
        """Return True if this analyzer applies to the project."""

    @abstractmethod
    def analyze(self) -> AnalysisResult:
        """Produce structured analysis for the project."""

    def _read_text(self, relative_path: str) -> str | None:
        path = self.project_root / relative_path
        if not path.is_file():
            return None
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None

    def _list_files(self, pattern: str, base: str = ".") -> list[str]:
        root = self.project_root / base
        if not root.is_dir():
            return []
        return sorted(str(p.relative_to(self.project_root)) for p in root.rglob(pattern))

    @staticmethod
    def format_markdown_section(title: str, body: str) -> str:
        return f"## {title}\n\n{body.strip()}\n"
