import asyncio
from unittest.mock import AsyncMock

import pytest

from bot.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_queue_worker_dispatches_in_order():
    bot = AsyncMock()
    limiter = RateLimiter(bot=bot, global_rate_per_sec=10, per_chat_cooldown_sec=0.0)
    await limiter.start()

    send_calls = []

    async def method_one(*args, **kwargs):
        send_calls.append("one")

    async def method_two(*args, **kwargs):
        send_calls.append("two")

    try:
        await limiter.enqueue_send(method_one, chat_id=1)
        await limiter.enqueue_send(method_two, chat_id=1)
        await asyncio.sleep(0.05)
    finally:
        await limiter.stop()

    assert send_calls == ["one", "two"]
