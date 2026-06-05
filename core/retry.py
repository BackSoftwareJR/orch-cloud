"""Retry utilities with exponential backoff."""

from __future__ import annotations

import logging
import random
import time
from collections.abc import Callable
from typing import TypeVar

from core.exceptions import RetryExhaustedError

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    func: Callable[[], T],
    *,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.25,
    retryable: tuple[type[Exception], ...] = (Exception,),
    operation_name: str = "operation",
) -> T:
    """Execute *func* with exponential backoff on retryable exceptions."""
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return func()
        except retryable as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            delay += random.uniform(0, jitter * delay)
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                operation_name,
                attempt,
                max_attempts,
                exc,
                delay,
            )
            time.sleep(delay)
    raise RetryExhaustedError(
        f"{operation_name} failed after {max_attempts} attempts: {last_exc}",
        remediation="Check network connectivity, Docker daemon, and credentials.",
    ) from last_exc
