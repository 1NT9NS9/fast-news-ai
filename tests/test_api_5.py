import pytest

from bot.services.rate_limiter import RateLimiter


class DummyBot:
    async def send_chat_action(self, *args, **kwargs):
        return None


def test_per_chat_cooldown_tracking():
    limiter = RateLimiter(bot=DummyBot(), per_chat_cooldown_sec=2.0)
    now = 50.0

    assert limiter.next_allowed_for_chat("chat", now) == pytest.approx(now)

    limiter.record_chat_send("chat", now)
    assert limiter.next_allowed_for_chat("chat", now) == pytest.approx(now + 2.0)

    limiter.record_chat_send("chat", now + 5.0)
    assert limiter.next_allowed_for_chat("chat", now + 5.0) == pytest.approx(now + 7.0)
