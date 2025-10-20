# python -m pytest tests (in terminal venv)
from bot.services.rate_limiter import RateLimiter


class DummyBot:
    async def send_chat_action(self, *args, **kwargs):
        return None


def test_global_sliding_window_allows_up_to_limit():
    limiter = RateLimiter(bot=DummyBot(), global_rate_per_sec=2)

    now = 100.0
    assert limiter.can_send_global(now)

    limiter.record_global(now)
    assert limiter.can_send_global(now + 0.01)

    limiter.record_global(now + 0.02)
    assert limiter.can_send_global(now + 0.5) is False

    # After one second the oldest entries expire.
    assert limiter.can_send_global(now + 1.05)
