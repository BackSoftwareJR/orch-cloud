"""Server configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEV_TOKEN = "dev-orchestrator-token-change-me"
JOBS_DIR = Path.home() / ".hyper-orchestrator" / "jobs"
DEFAULT_DATABASE_URL = f"sqlite:///{PROJECT_ROOT / 'orchestrator.db'}"


def get_api_token() -> str:
    return (
        os.environ.get("ORCHESTRATOR_API_TOKEN")
        or os.environ.get("WEBHOOK_TOKEN")
        or DEFAULT_DEV_TOKEN
    )


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_max_concurrent_jobs() -> int:
    raw = os.environ.get("MAX_CONCURRENT_JOBS", "3")
    try:
        value = int(raw)
    except ValueError:
        return 3
    return max(1, min(value, 32))


def get_require_api_token() -> bool:
    return os.environ.get("REQUIRE_API_TOKEN", "false").lower() in ("1", "true", "yes")


def get_webhook_secret() -> str | None:
    value = os.environ.get("WEBHOOK_SECRET", "").strip()
    return value or None


def get_cors_origins() -> list[str]:
    raw = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,https://backclub.it,https://www.backclub.it",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_max_debug_retries() -> int:
    raw = os.environ.get("MAX_DEBUG_RETRIES", "6")
    try:
        value = int(raw)
    except ValueError:
        return 6
    return max(1, min(value, 10))


def get_push_on_test_failure() -> bool:
    return os.environ.get("PUSH_ON_TEST_FAILURE", "false").lower() in ("1", "true", "yes")
