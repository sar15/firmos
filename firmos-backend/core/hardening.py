"""Production hardening utilities — idempotency, retry, rate limiter, dead-letter.

Apply to every connector write operation.
"""
from __future__ import annotations

import asyncio
import hashlib
import time
import uuid
from functools import wraps
from typing import Callable

from core.logging import log


# --- Idempotency ---

def generate_idempotency_key(firm_id: str, action: str, *args: str) -> str:
    """Generate a deterministic idempotency key for a connector write.
    
    Usage: key = generate_idempotency_key(firm_id, "create_bill", client_id, invoice_number)
    Store this key BEFORE calling the external API.
    """
    payload = f"{firm_id}:{action}:{':'.join(args)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


# ponytail: in-memory set as fast-path cache. DB is the authoritative check.
_used_keys: set[str] = set()


async def check_idempotency_db(pool, key: str) -> bool:
    """Returns True if duplicate. Uses DB UNIQUE constraint as source of truth."""
    if key in _used_keys:
        return True
    if not pool:
        # DB less mode fallback
        _used_keys.add(key)
        return False
        
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM audit_log WHERE idempotency_key = $1", key
        )
        if row is not None:
            _used_keys.add(key)
            return True
            
        # Normally inserted during the transaction. 
        # Add to fast-path cache.
        _used_keys.add(key)
        return False


# --- Retry with backoff ---

RETRY_DELAYS = [10, 20, 40]  # seconds — 3 retries with exponential backoff


def retry_with_backoff(
    max_retries: int = 3,
    delays: list[int] | None = None,
    never_retry_actions: set[str] | None = None,
):
    """Decorator for async functions: retry on failure with backoff.
    
    CRITICAL: never_retry_actions (e.g. {'file_gstr3b'}) are NEVER retried
    unless they have an idempotency key. This prevents duplicate filings.
    """
    delays = delays or RETRY_DELAYS
    never_retry = never_retry_actions or set()

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            action_name = func.__name__

            # Never auto-retry filing actions without idempotency
            if action_name in never_retry and "idempotency_key" not in kwargs:
                return await func(*args, **kwargs)

            last_exc = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = delays[min(attempt, len(delays) - 1)]
                        log.warning(
                            "retry_attempt",
                            action=action_name,
                            attempt=attempt + 1,
                            delay=delay,
                            error=str(exc),
                        )
                        await asyncio.sleep(delay)
                    else:
                        log.error(
                            "retry_exhausted",
                            action=action_name,
                            attempts=max_retries + 1,
                            error=str(exc),
                        )

            # Dead-letter: exhausted retries → raise with NEEDS_HUMAN flag
            raise DeadLetterError(
                f"Action '{action_name}' failed after {max_retries + 1} attempts",
                last_exception=last_exc,
            )

        return wrapper
    return decorator


# --- Rate limiter ---

class RateLimiter:
    """Per-connector, per-firm rate limiter using token bucket.
    
    ponytail: in-memory; production uses Redis EVALSHA for distributed limiting.
    """

    def __init__(self, calls_per_minute: int = 60):
        self._rate = calls_per_minute
        self._buckets: dict[str, list[float]] = {}

    async def acquire(self, firm_id: str, connector_id: str) -> None:
        """Block until rate limit allows. Raises if blocked too long (60s)."""
        key = f"{firm_id}:{connector_id}"
        now = time.monotonic()

        if key not in self._buckets:
            self._buckets[key] = []

        # Clean old entries (outside 60s window)
        self._buckets[key] = [t for t in self._buckets[key] if now - t < 60]

        if len(self._buckets[key]) >= self._rate:
            wait = 60 - (now - self._buckets[key][0])
            if wait > 60:
                raise RateLimitExceeded(f"Rate limit exceeded for {connector_id}")
            log.info("rate_limit_wait", connector=connector_id, wait_seconds=round(wait, 1))
            await asyncio.sleep(wait)

        self._buckets[key].append(time.monotonic())


# Singleton
rate_limiter = RateLimiter()


# --- Dead-letter ---

class DeadLetterError(Exception):
    """Raised when a connector action exhausts all retries.
    Workflow should set status = NEEDS_HUMAN, not silently drop."""

    def __init__(self, message: str, last_exception: Exception | None = None):
        super().__init__(message)
        self.last_exception = last_exception


class RateLimitExceeded(Exception):
    """Raised when per-firm rate limit is exceeded."""
    pass
