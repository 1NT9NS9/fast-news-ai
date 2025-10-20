import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import asyncio
import pytest

from scripts import validate_rate_limiter as validator


def test_parse_args_defaults_override():
    args = validator.parse_args(["--chats", "4", "--messages", "12"])
    assert args.chats == 4
    assert args.messages == 12
    assert args.global_rate == 30  # default untouched


@pytest.mark.asyncio
async def test_validation_dispatch_summary():
    bot = validator.DummyBot(send_latency=0.0)
    limiter = validator.RateLimiter(
        bot=bot,
        global_rate_per_sec=10,
        per_chat_cooldown_sec=0.01,
    )

    await limiter.start()
    try:
        await validator._dispatch_burst(limiter, bot, chats=1, messages_per_chat=3)
        summary = validator._summarize(bot)
        assert summary["total_messages"] == 3
        assert summary["per_chat"][1]["count"] == 3

        queue_metrics = await limiter.queue_metrics()
        assert queue_metrics["queue_depth"] == 0
    finally:
        await limiter.stop()
