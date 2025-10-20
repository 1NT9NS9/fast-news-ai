import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _reload_config(monkeypatch, *, value: str | None) -> Any:
    """Reload bot.utils.config with a specific env override."""
    module_name = "bot.utils.config"
    monkeypatch.delenv("ENABLE_RATE_LIMITED_QUEUE", raising=False)
    if value is not None:
        monkeypatch.setenv("ENABLE_RATE_LIMITED_QUEUE", value)
    sys.modules.pop(module_name, None)
    config = importlib.import_module(module_name)
    return config


def test_enable_rate_limited_queue_defaults_true(monkeypatch):
    config = _reload_config(monkeypatch, value=None)
    assert config.ENABLE_RATE_LIMITED_QUEUE is True


def test_enable_rate_limited_queue_respects_false_env(monkeypatch):
    config = _reload_config(monkeypatch, value="false")
    assert config.ENABLE_RATE_LIMITED_QUEUE is False
    # Restore default state for later tests.
    config = _reload_config(monkeypatch, value=None)
    assert config.ENABLE_RATE_LIMITED_QUEUE is True


@pytest.mark.asyncio
async def test_messenger_direct_send_without_limiter(monkeypatch):
    from bot.services import messenger as messenger_service

    class DummyBot:
        def __init__(self):
            self.messages = []

        async def send_message(self, chat_id, text, **kwargs):
            self.messages.append((chat_id, text, kwargs))
            return SimpleNamespace(message_id=1)

    dummy_bot = DummyBot()

    original_bot = getattr(messenger_service, "_bot", None)
    original_limiter = getattr(messenger_service, "_rate_limiter", None)

    messenger_service.configure(bot=dummy_bot, rate_limiter=None)
    try:
        result = await messenger_service.send_text(999, "hello", parse_mode="HTML")
        assert result.message_id == 1
        assert messenger_service.is_configured() is True
        assert dummy_bot.messages == [(999, "hello", {"parse_mode": "HTML"})]

        metrics = await messenger_service.get_queue_metrics()
        assert metrics["queue_depth"] == 0
        assert metrics["max_delay_sec"] == 0.0
        assert metrics["avg_delay_sec"] == 0.0
        assert metrics["max_delay_chat_id"] is None
    finally:
        messenger_service._bot = original_bot
        messenger_service._rate_limiter = original_limiter
