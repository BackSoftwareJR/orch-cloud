"""Laravel project analyzer."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from core.analyzers.base_analyzer import BaseAnalyzer
from core.models import AnalysisResult

logger = logging.getLogger(__name__)


class LaravelAnalyzer(BaseAnalyzer):
    """Parses composer.json, migrations, routes, models, and test config."""

    framework = "laravel"

    @classmethod
    def can_analyze(cls, project_root: Path) -> bool:
        return (project_root / "composer.json").is_file() and (
            (project_root / "artisan").is_file()
            or (project_root / "bootstrap" / "app.php").is_file()
        )

    def analyze(self) -> AnalysisResult:
        if not self._project_root_ready():
            return self._missing_project_result("php artisan test")

        composer = self._parse_composer()
        migrations = self._map_migrations()
        routes = self._identify_routes()
        models = self._list_models()
        controllers = self._list_controllers()
        providers = self._list_service_providers()
        env_vars = self._parse_env_example()
        test_info = self._detect_test_framework()
        php_version = composer.get("require", {}).get("php", "unknown")
        laravel_version = self._detect_laravel_version(composer)

        summary_lines = [
            f"- PHP requirement: `{php_version}`",
            f"- Laravel version: `{laravel_version}`",
            f"- Migrations found: {len(migrations)}",
            f"- Route files scanned: {len(routes)}",
            f"- Models found: {len(models)}",
            f"- Controllers found: {len(controllers)}",
            f"- Test framework: `{test_info['framework']}`",
        ]

        details: dict[str, object] = {
            "composer": composer,
            "migrations": migrations,
            "routes": routes,
            "models": models,
            "controllers": controllers,
            "service_providers": providers,
            "env_requirements": env_vars,
            "test_info": test_info,
            "laravel_version": laravel_version,
            "test_command": test_info["command"],
        }

        markdown = "\n".join(
            [
                self.format_markdown_section("Laravel Overview", "\n".join(summary_lines)),
                self.format_markdown_section("Dependencies", self._format_dependencies(composer)),
                self.format_markdown_section(
                    "Migrations",
                    self._format_list(migrations) or "_No migrations found._",
                ),
                self.format_markdown_section(
                    "Routes",
                    self._format_routes(routes) or "_No route files found._",
                ),
                self.format_markdown_section(
                    "Models",
                    self._format_file_list(models) or "_No models found._",
                ),
                self.format_markdown_section(
                    "Controllers",
                    self._format_file_list(controllers) or "_No controllers found._",
                ),
                self.format_markdown_section(
                    "Service Providers",
                    self._format_file_list(providers) or "_No custom providers found._",
                ),
                self.format_markdown_section(
                    "Environment",
                    self._format_env_vars(env_vars) or "_No .env.example found._",
                ),
                self.format_markdown_section(
                    "Testing",
                    self._format_testing(test_info),
                ),
            ]
        )

        return AnalysisResult(
            framework=self.framework,
            summary=markdown,
            details=details,
            confidence=1.0,
        )

    def _parse_composer(self) -> dict[str, object]:
        raw = self._read_text("composer.json")
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError as exc:
            logger.warning("Invalid composer.json: %s", exc)
        return {}

    def _detect_laravel_version(self, composer: dict[str, object]) -> str:
        require = composer.get("require", {})
        if not isinstance(require, dict):
            return "unknown"
        for key in ("laravel/framework", "illuminate/support"):
            if key in require:
                return str(require[key])
        return "unknown"

    def _map_migrations(self) -> list[dict[str, str]]:
        migration_files = self._list_files("*.php", "database/migrations")
        mapped: list[dict[str, str]] = []
        for rel_path in migration_files:
            name = Path(rel_path).stem
            table = self._extract_table_from_migration(rel_path)
            mapped.append({"file": rel_path, "name": name, "table": table or "unknown"})
        return mapped

    def _extract_table_from_migration(self, rel_path: str) -> str | None:
        content = self._read_text(rel_path)
        if not content:
            return None
        match = re.search(r"Schema::create\s*\(\s*['\"]([^'\"]+)['\"]", content)
        if match:
            return match.group(1)
        match = re.search(r"Schema::table\s*\(\s*['\"]([^'\"]+)['\"]", content)
        return match.group(1) if match else None

    def _identify_routes(self) -> list[dict[str, object]]:
        route_files: list[Path] = []
        for candidate in ("routes/web.php", "routes/api.php", "routes/console.php"):
            path = self.project_root / candidate
            if path.is_file():
                route_files.append(path)

        routes_dir = self.project_root / "routes"
        if routes_dir.exists() and routes_dir.is_dir():
            for path in routes_dir.glob("*.php"):
                if path not in route_files:
                    route_files.append(path)

        results: list[dict[str, object]] = []
        route_pattern = re.compile(
            r"Route::(get|post|put|patch|delete|match|resource|apiResource)\s*\(",
            re.IGNORECASE,
        )

        for path in sorted(route_files):
            content = self._read_text(str(path.relative_to(self.project_root))) or ""
            matches = route_pattern.findall(content)
            verbs = sorted(set(v.lower() for v in matches))
            results.append(
                {
                    "file": str(path.relative_to(self.project_root)),
                    "route_definitions": len(matches),
                    "verbs": verbs,
                }
            )
        return results

    def _list_models(self) -> list[str]:
        return self._list_files("*.php", "app/Models")[:40]

    def _list_controllers(self) -> list[str]:
        controllers = self._list_files("*.php", "app/Http/Controllers")
        if not controllers:
            controllers = self._list_files("*Controller.php", "app")
        return controllers[:40]

    def _list_service_providers(self) -> list[str]:
        providers = self._list_files("*Provider.php", "app/Providers")
        bootstrap = self.project_root / "bootstrap" / "providers.php"
        if bootstrap.is_file() and "bootstrap/providers.php" not in providers:
            providers.insert(0, "bootstrap/providers.php")
        return providers[:20]

    def _parse_env_example(self) -> list[str]:
        raw = self._read_text(".env.example")
        if not raw:
            return []
        vars_found: list[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                vars_found.append(line.split("=", 1)[0].strip())
        return vars_found[:50]

    def _detect_test_framework(self) -> dict[str, str]:
        composer = self._parse_composer()
        require = composer.get("require-dev", {})
        if not isinstance(require, dict):
            require = {}
        require_all = {**composer.get("require", {}), **require}
        if not isinstance(require_all, dict):
            require_all = {}

        if "pestphp/pest" in require_all:
            return {"framework": "Pest", "command": "./vendor/bin/pest"}
        if "phpunit/phpunit" in require_all:
            if (self.project_root / "artisan").is_file():
                return {"framework": "PHPUnit (Artisan)", "command": "php artisan test"}
            return {"framework": "PHPUnit", "command": "./vendor/bin/phpunit"}
        if (self.project_root / "artisan").is_file():
            return {"framework": "Artisan", "command": "php artisan test"}
        return {"framework": "unknown", "command": "php artisan test"}

    def _format_dependencies(self, composer: dict[str, object]) -> str:
        require = composer.get("require", {})
        if not isinstance(require, dict) or not require:
            return "_No dependencies listed._"
        lines = [f"- `{name}`: `{version}`" for name, version in sorted(require.items())]
        return "\n".join(lines)

    @staticmethod
    def _format_list(items: list[dict[str, str]]) -> str:
        if not items:
            return ""
        lines = [f"- `{item['file']}` → table `{item['table']}`" for item in items]
        return "\n".join(lines)

    @staticmethod
    def _format_file_list(files: list[str]) -> str:
        if not files:
            return ""
        return "\n".join(f"- `{f}`" for f in files)

    @staticmethod
    def _format_routes(routes: list[dict[str, object]]) -> str:
        if not routes:
            return ""
        lines = []
        for route in routes:
            verbs = ", ".join(route.get("verbs", []))  # type: ignore[arg-type]
            lines.append(
                f"- `{route['file']}`: {route['route_definitions']} definitions ({verbs})"
            )
        return "\n".join(lines)

    @staticmethod
    def _format_env_vars(vars_found: list[str]) -> str:
        if not vars_found:
            return ""
        return "\n".join(f"- `{v}`" for v in vars_found)

    @staticmethod
    def _format_testing(test_info: dict[str, str]) -> str:
        return (
            f"- Framework: `{test_info['framework']}`\n"
            f"- Recommended command: `{test_info['command']}`"
        )
