# -*- coding: utf-8 -*-
from datetime import datetime, timezone
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers.news import news_command_internal
from bot.services import messenger as messenger_service
from bot.utils.config import MAX_NEWS_REQUESTS_PER_DAY


@pytest.mark.asyncio
async def test_api_14_news_rate_limit_message_queued(monkeypatch):
    """Verify /news limit branch sends via messenger queue instead of direct replies."""
    user_id = 123
    chat_id = 456
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    class DummyStorage:
        async def load_user_data(self):
            return {
                str(user_id): {
                    "last_news_date": today,
                    "news_request_count": MAX_NEWS_REQUESTS_PER_DAY,
                }
            }

    dummy_storage = DummyStorage()
    monkeypatch.setattr("bot.handlers.news.StorageService", lambda: dummy_storage)
    monkeypatch.setattr("bot.handlers.news.AIService", lambda: SimpleNamespace())
    monkeypatch.setattr("bot.handlers.news.ScraperService", lambda: SimpleNamespace())
    monkeypatch.setattr("bot.handlers.news.ClusteringService", lambda: SimpleNamespace())

    send_mock = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(messenger_service, "send_text", send_mock)

    update = SimpleNamespace(
        callback_query=None,
        effective_user=SimpleNamespace(id=user_id, username="tester"),
        effective_chat=SimpleNamespace(id=chat_id),
        message=None,
    )
    context = SimpleNamespace()

    await news_command_internal(update, context)

    send_mock.assert_awaited_once()
    args, kwargs = send_mock.await_args
    assert args[0] == chat_id
    assert "лимита" in args[1]
    assert kwargs == {}
