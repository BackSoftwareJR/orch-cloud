"""Auto-detect project framework with confidence scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from core.analyzers.base_analyzer import BaseAnalyzer
from core.analyzers.laravel_analyzer import LaravelAnalyzer
from core.analyzers.nextjs_analyzer import NextJsAnalyzer
from core.models import FrameworkType

ANALYZERS: list[type[BaseAnalyzer]] = [LaravelAnalyzer, NextJsAnalyzer]


@dataclass(frozen=True)
class FrameworkDetection:
    """Framework detection result with confidence."""

    framework: FrameworkType
    confidence: float
    analyzer: type[BaseAnalyzer] | None
    signals: dict[str, bool]


def detect_framework(project_root: Path) -> FrameworkDetection:
    """Score Laravel vs Next.js vs unknown and return best match."""
    root = project_root.resolve()
    signals = _collect_signals(root)

    laravel_score = _score_laravel(signals)
    nextjs_score = _score_nextjs(signals)

    if laravel_score >= nextjs_score and laravel_score >= 0.5:
        return FrameworkDetection(
            framework="laravel",
            confidence=laravel_score,
            analyzer=LaravelAnalyzer,
            signals=signals,
        )
    if nextjs_score > laravel_score and nextjs_score >= 0.5:
        return FrameworkDetection(
            framework="nextjs",
            confidence=nextjs_score,
            analyzer=NextJsAnalyzer,
            signals=signals,
        )

    return FrameworkDetection(
        framework="unknown",
        confidence=max(laravel_score, nextjs_score, 0.1),
        analyzer=None,
        signals=signals,
    )


def select_analyzer(project_root: Path) -> BaseAnalyzer:
    """Select the best analyzer for a project."""
    from core.analyzers.unknown_analyzer import UnknownAnalyzer

    detection = detect_framework(project_root)
    if detection.analyzer is not None:
        return detection.analyzer(project_root)
    return UnknownAnalyzer(project_root)


def _collect_signals(root: Path) -> dict[str, bool]:
    if not root.exists() or not root.is_dir():
        return {
            "composer_json": False,
            "artisan": False,
            "bootstrap_app": False,
            "package_json": False,
            "next_config": False,
            "app_router_dir": False,
            "pages_router_dir": False,
            "next_dependency": False,
        }

    has_composer = (root / "composer.json").is_file()
    has_artisan = (root / "artisan").is_file()
    has_bootstrap = (root / "bootstrap" / "app.php").is_file()
    has_package = (root / "package.json").is_file()
    has_next_config = any(
        (root / name).is_file() for name in ("next.config.js", "next.config.mjs", "next.config.ts")
    )
    has_app_dir = (root / "app").is_dir() or (root / "src" / "app").is_dir()
    has_pages_dir = (root / "pages").is_dir() or (root / "src" / "pages").is_dir()
    has_next_dep = False

    if has_package:
        try:
            data = json.loads((root / "package.json").read_text(encoding="utf-8"))
            deps = {**(data.get("dependencies") or {}), **(data.get("devDependencies") or {})}
            has_next_dep = "next" in deps
        except (OSError, json.JSONDecodeError):
            pass

    return {
        "composer_json": has_composer,
        "artisan": has_artisan,
        "bootstrap_app": has_bootstrap,
        "package_json": has_package,
        "next_config": has_next_config,
        "app_router_dir": has_app_dir,
        "pages_router_dir": has_pages_dir,
        "next_dependency": has_next_dep,
    }


def _score_laravel(signals: dict[str, bool]) -> float:
    score = 0.0
    if signals["composer_json"]:
        score += 0.35
    if signals["artisan"]:
        score += 0.35
    if signals["bootstrap_app"]:
        score += 0.2
    if signals["composer_json"] and not signals["next_dependency"]:
        score += 0.1
    return min(score, 1.0)


def _score_nextjs(signals: dict[str, bool]) -> float:
    score = 0.0
    if signals["next_dependency"]:
        score += 0.45
    if signals["next_config"]:
        score += 0.2
    if signals["app_router_dir"]:
        score += 0.2
    if signals["pages_router_dir"]:
        score += 0.15
    if signals["package_json"]:
        score += 0.1
    return min(score, 1.0)
