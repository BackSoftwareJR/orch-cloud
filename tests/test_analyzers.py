"""Unit tests for framework analyzers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.analyzers.detector import detect_framework
from core.analyzers.laravel_analyzer import LaravelAnalyzer
from core.analyzers.nextjs_analyzer import NextJsAnalyzer


@pytest.fixture
def laravel_project(tmp_path: Path) -> Path:
    root = tmp_path / "laravel-app"
    root.mkdir()
    (root / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    (root / "composer.json").write_text(
        json.dumps(
            {
                "require": {"php": "^8.2", "laravel/framework": "^11.0"},
                "require-dev": {"pestphp/pest": "^3.0"},
            }
        ),
        encoding="utf-8",
    )
    migrations = root / "database" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "2024_01_01_create_users_table.php").write_text(
        "Schema::create('users', function() {});",
        encoding="utf-8",
    )
    routes = root / "routes"
    routes.mkdir()
    (routes / "web.php").write_text("Route::get('/users', fn() => []);", encoding="utf-8")
    models = root / "app" / "Models"
    models.mkdir(parents=True)
    (models / "User.php").write_text("class User {}", encoding="utf-8")
    (root / ".env.example").write_text("APP_KEY=\nDB_DATABASE=laravel\n", encoding="utf-8")
    return root


@pytest.fixture
def nextjs_project(tmp_path: Path) -> Path:
    root = tmp_path / "next-app"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {"next": "^14.0.0", "react": "^18.0.0"},
                "devDependencies": {"vitest": "^1.0.0"},
                "scripts": {"test": "vitest run", "dev": "next dev"},
            }
        ),
        encoding="utf-8",
    )
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "page.tsx").write_text("export default function Home() {}", encoding="utf-8")
    (app_dir / "api" / "hello").mkdir(parents=True)
    (app_dir / "api" / "hello" / "route.ts").write_text(
        "export async function GET() {}", encoding="utf-8"
    )
    (root / "middleware.ts").write_text("export function middleware() {}", encoding="utf-8")
    (root / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"paths": {"@/*": ["./src/*"]}}}),
        encoding="utf-8",
    )
    (root / "vitest.config.ts").write_text("export default {}", encoding="utf-8")
    return root


def test_laravel_analyzer_detects_framework(laravel_project: Path) -> None:
    assert LaravelAnalyzer.can_analyze(laravel_project)
    result = LaravelAnalyzer(laravel_project).analyze()
    assert result.framework == "laravel"
    assert "Laravel Overview" in result.summary
    assert "users" in result.summary.lower()
    assert result.details["test_command"] == "./vendor/bin/pest"


def test_nextjs_analyzer_detects_vitest(nextjs_project: Path) -> None:
    assert NextJsAnalyzer.can_analyze(nextjs_project)
    result = NextJsAnalyzer(nextjs_project).analyze()
    assert result.framework == "nextjs"
    assert "Vitest" in result.summary
    assert "middleware.ts" in result.summary
    assert result.details["test_command"] == "npm run test"


def test_framework_detector_confidence(laravel_project: Path, nextjs_project: Path) -> None:
    laravel_detection = detect_framework(laravel_project)
    assert laravel_detection.framework == "laravel"
    assert laravel_detection.confidence >= 0.5

    next_detection = detect_framework(nextjs_project)
    assert next_detection.framework == "nextjs"
    assert next_detection.confidence >= 0.5
