import asyncio
from unittest.mock import AsyncMock

import pytest
from telegram.error import RetryAfter

from bot.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_retry_after_requeues_with_backoff(monkeypatch, event_loop):
    bot = AsyncMock()
    limiter = RateLimiter(
        bot=bot,
        global_rate_per_sec=10,
        per_chat_cooldown_sec=0.0,
        loop=event_loop,
    )
    limiter._retry_base_delay = 0.01  # accelerate tests
    limiter._max_retry_attempts = 2

    await limiter.start()

    call_counter = {"count": 0}

    async def flaky_send(*args, **kwargs):
        call_counter["count"] += 1
        if call_counter["count"] == 1:
            # Support both old and new python-telegram-bot RetryAfter signatures
            try:
                exc = RetryAfter(retry_after=0.03, message="slow down")
            except TypeError:
                exc = RetryAfter(0.03)
            raise exc

    try:
        await limiter.enqueue_send(flaky_send, chat_id=123)
        await asyncio.sleep(0.02)
        assert call_counter["count"] == 1

        await asyncio.sleep(0.05)
    finally:
        await limiter.stop()

    assert call_counter["count"] == 2
