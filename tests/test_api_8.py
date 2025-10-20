import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_send_records_global_and_chat_state(event_loop):
    bot = AsyncMock()
    limiter = RateLimiter(
        bot=bot,
        global_rate_per_sec=10,
        per_chat_cooldown_sec=0.0,
        loop=event_loop,
    )
    await limiter.start()

    send_method = AsyncMock()

    try:
        await limiter.enqueue_send(send_method, chat_id="chat")
        await asyncio.sleep(0.05)
    finally:
        await limiter.stop()

    assert send_method.await_count == 1
    now = event_loop.time()
    assert limiter.can_send_global(now)
    assert limiter.next_allowed_for_chat("chat", now) >= now
