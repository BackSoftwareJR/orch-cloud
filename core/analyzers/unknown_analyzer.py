"""Fallback analyzer for unrecognized project types."""

from __future__ import annotations

from pathlib import Path

from core.analyzers.base_analyzer import BaseAnalyzer
from core.models import AnalysisResult, FrameworkType


class UnknownAnalyzer(BaseAnalyzer):
    """Fallback analyzer for unrecognized project types."""

    framework: FrameworkType = "unknown"

    @classmethod
    def can_analyze(cls, project_root: Path) -> bool:
        return True

    def analyze(self) -> AnalysisResult:
        files = sorted(
            p.name
            for p in self.project_root.iterdir()
            if p.is_file() and not p.name.startswith(".")
        )[:30]
        summary = self.format_markdown_section(
            "Unknown Framework",
            "Could not detect Laravel or Next.js with sufficient confidence.\n\n"
            f"Top-level files: {', '.join(files) or 'none'}",
        )
        return AnalysisResult(
            framework="unknown",
            summary=summary,
            details={"test_command": "npm run test"},
            confidence=0.0,
        )
