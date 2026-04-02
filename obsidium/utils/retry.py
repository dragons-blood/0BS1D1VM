"""
Retry utilities for resilient API calls.

Provides exponential backoff with jitter for transient failures
like rate limits, timeouts, and server errors.
"""

from __future__ import annotations

import asyncio
import random
import functools
from typing import TypeVar, Callable, Any

import httpx


T = TypeVar("T")

# HTTP status codes that are worth retrying
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


async def retry_async(
    fn: Callable[..., Any],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: float = 0.5,
    retryable_exceptions: tuple = (
        httpx.TimeoutException,
        httpx.ConnectError,
        httpx.ReadTimeout,
    ),
    **kwargs: Any,
) -> Any:
    """Call an async function with exponential backoff retry.

    Args:
        fn: Async function to call.
        *args: Positional arguments for fn.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds.
        max_delay: Maximum delay cap in seconds.
        jitter: Random jitter factor (0-1).
        retryable_exceptions: Exception types that trigger a retry.
        **kwargs: Keyword arguments for fn.

    Returns:
        The result of fn(*args, **kwargs).

    Raises:
        The last exception if all retries are exhausted.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            result = await fn(*args, **kwargs)
            return result
        except httpx.HTTPStatusError as e:
            if e.response.status_code in RETRYABLE_STATUS_CODES:
                last_exception = e
                if attempt < max_retries:
                    # Check for Retry-After header
                    retry_after = e.response.headers.get("retry-after")
                    if retry_after:
                        try:
                            delay = float(retry_after)
                        except ValueError:
                            delay = base_delay * (2 ** attempt)
                    else:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                    delay += random.uniform(0, jitter * delay)
                    await asyncio.sleep(delay)
                    continue
            raise  # Non-retryable HTTP error
        except retryable_exceptions as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(base_delay * (2 ** attempt), max_delay)
                delay += random.uniform(0, jitter * delay)
                await asyncio.sleep(delay)
                continue

    raise last_exception  # type: ignore[misc]
