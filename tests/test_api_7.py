import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_requeue_when_global_limit_reached(event_loop):
    bot = AsyncMock()
    limiter = RateLimiter(
        bot=bot,
        global_rate_per_sec=1,
        per_chat_cooldown_sec=0.0,
        loop=event_loop,
    )
    await limiter.start()

    send_method = AsyncMock()

    # Fill the global window to hit the limit.
    limiter.record_global(event_loop.time())

    try:
        await limiter.enqueue_send(send_method, chat_id=1)

        await asyncio.sleep(0.05)
        assert send_method.await_count == 0

        await asyncio.sleep(1.1)
        await asyncio.sleep(0.05)
    finally:
        await limiter.stop()

    assert send_method.await_count == 1
