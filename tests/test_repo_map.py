"""Tests for repository map generation and context integration."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from core.context_builder import (
    DEFAULT_CONTEXT_BUDGET,
    build_agent_context,
    is_slim_context_enabled,
)
from core.models import AgentPreset
from core.repo_map import (
    build_repo_map,
    clear_repo_map_cache,
    format_repo_map_summary,
    get_repo_map,
)


@pytest.fixture(autouse=True)
def _clear_repo_map_cache() -> None:
    clear_repo_map_cache()
    yield
    clear_repo_map_cache()


@pytest.fixture
def laravel_project(tmp_path: Path) -> Path:
    root = tmp_path / "laravel-app"
    root.mkdir()
    (root / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    (root / "composer.json").write_text(
        json.dumps({"require": {"php": "^8.2", "laravel/framework": "^11.0"}}),
        encoding="utf-8",
    )
    migrations = root / "database" / "migrations"
    migrations.mkdir(parents=True)
    (migrations / "2024_01_01_create_users_table.php").write_text("migration", encoding="utf-8")
    routes = root / "routes"
    routes.mkdir()
    (routes / "web.php").write_text("Route::get('/users');", encoding="utf-8")
    (routes / "api.php").write_text("Route::get('/api/users');", encoding="utf-8")
    models = root / "app" / "Models"
    models.mkdir(parents=True)
    (models / "User.php").write_text("class User {}", encoding="utf-8")
    controllers = root / "app" / "Http" / "Controllers"
    controllers.mkdir(parents=True)
    (controllers / "UserController.php").write_text("class UserController {}", encoding="utf-8")
    return root


@pytest.fixture
def nextjs_project(tmp_path: Path) -> Path:
    root = tmp_path / "next-app"
    root.mkdir()
    (root / "package.json").write_text(
        json.dumps(
            {
                "dependencies": {"next": "^14.0.0", "react": "^18.0.0"},
                "scripts": {"dev": "next dev"},
            }
        ),
        encoding="utf-8",
    )
    components = root / "components"
    components.mkdir()
    (components / "Header.tsx").write_text("export function Header() {}", encoding="utf-8")
    pages = root / "pages"
    pages.mkdir()
    (pages / "index.tsx").write_text("export default function Home() {}", encoding="utf-8")
    app_dir = root / "app"
    app_dir.mkdir()
    (app_dir / "layout.tsx").write_text("export default function Layout() {}", encoding="utf-8")
    return root


def test_build_repo_map_laravel_structure(laravel_project: Path) -> None:
    repo_map = build_repo_map(laravel_project)

    assert repo_map["schema_version"] == "1.0"
    assert repo_map["stack"]["primary"] == "laravel"
    assert "routes" in repo_map["top_level_dirs"]
    assert "composer.json" in repo_map["key_files"]
    module_paths = {module["path"] for module in repo_map["modules"]}
    assert "app/Models" in module_paths
    assert "routes" in module_paths


def test_build_repo_map_nextjs_structure(nextjs_project: Path) -> None:
    repo_map = build_repo_map(nextjs_project)

    assert repo_map["stack"]["primary"] == "nextjs"
    assert "package.json" in repo_map["key_files"]
    module_paths = {module["path"] for module in repo_map["modules"]}
    assert "components" in module_paths
    assert "pages" in module_paths


def test_get_repo_map_uses_mtime_cache(laravel_project: Path) -> None:
    first = get_repo_map(laravel_project)
    second = get_repo_map(laravel_project)
    assert first is second

    (laravel_project / "composer.json").write_text(
        json.dumps({"require": {"php": "^8.3", "laravel/framework": "^12.0"}}),
        encoding="utf-8",
    )
    refreshed = get_repo_map(laravel_project)
    assert refreshed is not first


def test_format_repo_map_summary_preset_focus(laravel_project: Path) -> None:
    repo_map = build_repo_map(laravel_project)

    backend_summary = format_repo_map_summary(repo_map, preset=AgentPreset.BACKEND)
    ux_summary = format_repo_map_summary(repo_map, preset=AgentPreset.UX)

    assert "* app/Models" in backend_summary
    assert "* routes" in backend_summary
    assert "* app/Models" not in ux_summary or "* components" not in backend_summary


def test_format_repo_map_summary_ux_focus(nextjs_project: Path) -> None:
    repo_map = build_repo_map(nextjs_project)
    summary = format_repo_map_summary(repo_map, preset=AgentPreset.UX)

    assert "* components" in summary
    assert "* pages" in summary or "* app" in summary


def test_build_agent_context_includes_repo_map(laravel_project: Path) -> None:
    analysis = "## Laravel Overview\n\n- PHP project\n\n## Models\n\n- User"
    context = build_agent_context(
        laravel_project,
        analysis,
        task="Add user endpoint",
        preset=AgentPreset.BACKEND,
    )

    assert "## Repository map" in context
    assert "## Project context" in context
    assert "Laravel Overview" in context or "Models" in context
    assert len(context) <= DEFAULT_CONTEXT_BUDGET + 200


def test_slim_context_skips_heavy_excerpt(laravel_project: Path) -> None:
    analysis = "## Laravel Overview\n\n" + ("detail " * 2000)
    with patch.dict(os.environ, {"SLIM_CONTEXT": "true"}, clear=False):
        assert is_slim_context_enabled()
        context = build_agent_context(
            laravel_project,
            analysis,
            task="Add user endpoint",
            preset=AgentPreset.BACKEND,
        )

    assert "## Repository map" in context
    assert "## Project context" not in context
    assert "detail detail" not in context
    assert len(context) < len(analysis)


def test_build_repo_map_respects_max_files(tmp_path: Path) -> None:
    root = tmp_path / "many-files"
    root.mkdir()
    for idx in range(30):
        (root / f"file_{idx}.txt").write_text("x", encoding="utf-8")

    repo_map = build_repo_map(root, max_files=10)
    assert repo_map["file_count"] == 10
    assert repo_map["truncated"] is True
