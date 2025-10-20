from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers import manage


@pytest.mark.asyncio
async def test_manage_add_channel_routes_through_messenger(monkeypatch):
    send_mock = AsyncMock()
    monkeypatch.setattr(manage.messenger_service, "send_text", send_mock)

    class DummyStorage:
        async def load_user_data(self):
            return {}

        async def save_user_data(self, data):
            return None

    monkeypatch.setattr(manage, "StorageService", lambda: DummyStorage())
    monkeypatch.setattr(manage, "ScraperService", lambda: None)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=42, username="tester"),
        effective_chat=SimpleNamespace(id=123),
        message=SimpleNamespace(message_id=7),
    )
    context = SimpleNamespace(args=[])

    await manage.add_channel_command(update, context)

    assert send_mock.await_count == 1
    args, kwargs = send_mock.await_args
    assert args[0] == 123
    assert "@channelname" in args[1]
