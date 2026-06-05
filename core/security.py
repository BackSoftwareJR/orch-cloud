"""Security helpers: URL validation, prompt sanitization, secret redaction."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from core.exceptions import SecurityError

_REPO_URL_PATTERN = re.compile(
    r"^(https?://[\w.\-]+(?:/[\w.\-~]+)+(?:\.git)?|git@[\w.\-]+:[\w.\-/]+(?:\.git)?)$",
    re.IGNORECASE,
)

_SHELL_METACHAR_PATTERN = re.compile(r"[;&|`$(){}<>\\]")
_SECRET_PATTERNS = (
    re.compile(r"(api[_-]?key\s*[=:]\s*)[\w\-]+", re.IGNORECASE),
    re.compile(r"(token\s*[=:]\s*)[\w\-]+", re.IGNORECASE),
    re.compile(r"(password\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(secret\s*[=:]\s*)\S+", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)


def validate_repo_url(repo_url: str) -> str:
    """Validate and normalize a Git repository URL."""
    url = repo_url.strip()
    if not url:
        raise SecurityError(
            "Repository URL is empty.",
            remediation="Provide a valid HTTPS or SSH Git URL, e.g. https://github.com/org/repo.git",
        )
    if _SHELL_METACHAR_PATTERN.search(url):
        raise SecurityError(
            "Repository URL contains invalid shell characters.",
            remediation="Use a plain HTTPS or git@ URL without shell metacharacters.",
        )
    if not _REPO_URL_PATTERN.match(url):
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return url
        if url.startswith("git@"):
            return url
        raise SecurityError(
            f"Invalid repository URL: {url!r}",
            remediation="Use https://github.com/org/repo.git or git@github.com:org/repo.git",
        )
    return url


def sanitize_task_prompt(task: str, *, max_length: int = 8000) -> str:
    """Sanitize user task text before passing to shell/agent."""
    cleaned = task.strip()
    if not cleaned:
        raise SecurityError(
            "Task description is empty.",
            remediation="Provide a natural-language task description via --task.",
        )
    if len(cleaned) > max_length:
        raise SecurityError(
            f"Task description exceeds {max_length} characters.",
            remediation="Shorten the task or split it into multiple runs.",
        )
    if "\x00" in cleaned:
        cleaned = cleaned.replace("\x00", "")
    return cleaned


def redact_secrets(text: str) -> str:
    """Redact likely API keys and tokens from log output."""
    redacted = text
    for pattern in _SECRET_PATTERNS[:-1]:
        redacted = pattern.sub(r"\1***REDACTED***", redacted)
    redacted = _SECRET_PATTERNS[-1].sub("sk-***REDACTED***", redacted)
    return redacted


def check_ssh_key_permissions(ssh_dir: Path) -> list[str]:
    """Return warnings for SSH keys with overly permissive file modes."""
    warnings: list[str] = []
    if not ssh_dir.is_dir():
        return warnings
    for key_file in ssh_dir.glob("*"):
        if not key_file.is_file() or key_file.suffix == ".pub":
            continue
        if key_file.name in ("config", "known_hosts", "authorized_keys"):
            continue
        try:
            mode = key_file.stat().st_mode & 0o777
            if mode & 0o077:
                warnings.append(
                    f"SSH key {key_file} has mode {oct(mode)} — should be 0600 or tighter. "
                    "Run: chmod 600 {key_file}"
                )
        except OSError:
            continue
    return warnings
