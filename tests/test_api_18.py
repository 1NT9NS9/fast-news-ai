import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from bot.services import rate_limiter
from bot.services.rate_limiter import RateLimiter, _QueueEntry


class DummyBot:
    def __init__(self):
        self.chat_actions = []
        self.messages = []

    async def send_chat_action(self, chat_id, action):
        self.chat_actions.append((chat_id, action))

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))
        return SimpleNamespace(message_id=1)


@pytest.mark.asyncio
async def test_queue_metrics_and_alert(monkeypatch):
    bot = DummyBot()
    limiter = RateLimiter(bot, global_rate_per_sec=30, per_chat_cooldown_sec=1.0)

    loop = asyncio.get_running_loop()
    limiter._queue_lock = asyncio.Lock()
    limiter._queue_event = asyncio.Event()

    now = loop.time()

    async def noop_method(*args, **kwargs):
        return None

    entry_one = _QueueEntry(
        method=noop_method,
        chat_id=1001,
        args=(),
        kwargs={},
        context=None,
        future=loop.create_future(),
        enqueued_at=now - 1.0,
        ready_at=now + 3.0,
    )
    entry_two = _QueueEntry(
        method=noop_method,
        chat_id=2002,
        args=(),
        kwargs={},
        context=None,
        future=loop.create_future(),
        enqueued_at=now - 0.5,
        ready_at=now + 1.5,
    )

    limiter._queue = []
    rate_limiter.heapq.heappush(limiter._queue, (entry_one.ready_at, 1, entry_one))
    rate_limiter.heapq.heappush(limiter._queue, (entry_two.ready_at, 2, entry_two))

    metrics = await limiter.queue_metrics()

    assert metrics["queue_depth"] == 2
    assert pytest.approx(metrics["max_delay_sec"], rel=1e-3) == 3.0
    assert pytest.approx(metrics["avg_delay_sec"], rel=1e-3) == pytest.approx((3.0 + 1.5) / 2, rel=1e-3)
    assert metrics["max_delay_chat_id"] == 1001
    assert pytest.approx(metrics["max_delay_chat_sec"], rel=1e-3) == 3.0

    limiter._admin_chat_id_log = 999
    limiter._delay_alert_threshold = 1.0
    limiter._last_delay_alert_at = None

    await limiter._maybe_notify_delay(metrics)
    await asyncio.sleep(0)

    assert len(bot.messages) == 1
    chat_id, text = bot.messages[0]
    assert chat_id == 999
    assert "Warning: rate limiter backlog detected." in text
    assert "Queue depth: 2" in text
