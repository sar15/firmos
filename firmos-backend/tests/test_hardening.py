"""Tests for production hardening: idempotency, retry, rate limiter, dead-letter."""

import pytest
import asyncio


# ---- Idempotency ----

def test_idempotency_key_deterministic():
    """Same inputs produce same key."""
    from core.hardening import generate_idempotency_key
    k1 = generate_idempotency_key("firm-1", "create_bill", "client-1", "INV-001")
    k2 = generate_idempotency_key("firm-1", "create_bill", "client-1", "INV-001")
    assert k1 == k2


def test_idempotency_key_different():
    """Different inputs produce different keys."""
    from core.hardening import generate_idempotency_key
    k1 = generate_idempotency_key("firm-1", "create_bill", "client-1", "INV-001")
    k2 = generate_idempotency_key("firm-1", "create_bill", "client-1", "INV-002")
    assert k1 != k2


@pytest.mark.asyncio
async def test_idempotency_check():
    """First use returns False, second returns True."""
    from core.hardening import check_idempotency_db, _used_keys
    key = "test" + "-unique-key-123"
    _used_keys.discard(key)  # clean up

    assert await check_idempotency_db(None, key) is False  # fresh
    assert await check_idempotency_db(None, key) is True   # duplicate


# ---- Retry ----

@pytest.mark.asyncio
async def test_retry_succeeds_on_second_try():
    """Function that fails once, then succeeds — should return success."""
    from core.hardening import retry_with_backoff

    attempt_count = 0

    @retry_with_backoff(max_retries=2, delays=[0, 0])
    async def flaky():
        nonlocal attempt_count
        attempt_count += 1
        if attempt_count < 2:
            raise ConnectionError("temporary failure")
        return "success"

    result = await flaky()
    assert result == "success"
    assert attempt_count == 2


@pytest.mark.asyncio
async def test_retry_exhausted_raises_dead_letter():
    """Function that always fails → DeadLetterError."""
    from core.hardening import retry_with_backoff, DeadLetterError

    @retry_with_backoff(max_retries=1, delays=[0])
    async def always_fails():
        raise ConnectionError("permanent failure")

    with pytest.raises(DeadLetterError, match="failed after 2 attempts"):
        await always_fails()


# ---- Rate Limiter ----

@pytest.mark.asyncio
async def test_rate_limiter_allows_within_limit():
    """Calls within rate limit should not block."""
    from core.hardening import RateLimiter
    limiter = RateLimiter(calls_per_minute=100)

    # 5 calls should be instant
    for _ in range(5):
        await limiter.acquire("firm-1", "zoho")


# ---- Dead Letter ----

def test_dead_letter_error_has_last_exception():
    """DeadLetterError stores the original exception."""
    from core.hardening import DeadLetterError
    original = ConnectionError("network timeout")
    err = DeadLetterError("failed after retries", last_exception=original)
    assert err.last_exception is original
