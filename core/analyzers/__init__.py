"""Framework-specific project analyzers."""

from core.analyzers.base_analyzer import BaseAnalyzer
from core.analyzers.detector import detect_framework, select_analyzer
from core.analyzers.laravel_analyzer import LaravelAnalyzer
from core.analyzers.nextjs_analyzer import NextJsAnalyzer
from core.analyzers.unknown_analyzer import UnknownAnalyzer

__all__ = [
    "BaseAnalyzer",
    "LaravelAnalyzer",
    "NextJsAnalyzer",
    "UnknownAnalyzer",
    "detect_framework",
    "select_analyzer",
]
