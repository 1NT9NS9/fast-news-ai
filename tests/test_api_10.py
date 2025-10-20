import asyncio
from unittest.mock import AsyncMock

import pytest

import bot.services.rate_limiter as rate_limiter_module
from bot.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_typing_indicator_sent_on_heavy_delay(monkeypatch, event_loop):
    monkeypatch.setattr(rate_limiter_module, "HEAVY_LOAD_DELAY_THRESHOLD_SEC", 0.01)

    bot = AsyncMock()
    limiter = RateLimiter(
        bot=bot,
        global_rate_per_sec=10,
        per_chat_cooldown_sec=0.05,
        loop=event_loop,
    )
    await limiter.start()

    typing_mock = AsyncMock()
    limiter._send_typing_indicator = typing_mock

    limiter.record_chat_send("chat", event_loop.time())

    send_method = AsyncMock()

    try:
        await limiter.enqueue_send(send_method, chat_id="chat")
        await asyncio.sleep(0.02)
    finally:
        await limiter.stop()

    typing_mock.assert_awaited_once()
