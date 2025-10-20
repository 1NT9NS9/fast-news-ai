from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from bot.handlers import log as log_handler
from bot.handlers import start


@pytest.mark.asyncio
async def test_start_command_uses_messenger(monkeypatch):
    send_mock = AsyncMock()
    monkeypatch.setattr(start.messenger_service, "send_text", send_mock)

    class DummyStorage:
        def __init__(self):
            self.saved = None

        async def load_user_data(self):
            return {}

        async def save_user_data(self, data):
            self.saved = data

    monkeypatch.setattr(start, "StorageService", DummyStorage)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=7, username="tester"),
        effective_chat=SimpleNamespace(id=900),
        message=SimpleNamespace(message_id=11),
    )
    context = SimpleNamespace()

    await start.start_command(update, context)

    assert send_mock.await_count == 2
    first_call = send_mock.await_args_list[0]
    second_call = send_mock.await_args_list[1]
    assert first_call.args[0] == 900
    assert second_call.args[0] == 900
    assert "Выберите действие" in second_call.args[1]


@pytest.mark.asyncio
async def test_log_command_rejects_non_admin_via_messenger(monkeypatch):
    send_mock = AsyncMock()
    monkeypatch.setattr(log_handler.messenger_service, "send_text", send_mock)
    monkeypatch.setenv("ADMIN_CHAT_ID_BACKUP", "101")

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=202, username="not_admin"),
        effective_chat=SimpleNamespace(id=501),
        message=SimpleNamespace(message_id=15),
    )
    context = SimpleNamespace()

    await log_handler.log_command(update, context)

    assert send_mock.await_count == 1
    args, kwargs = send_mock.await_args
    assert args[0] == 501
    assert "доступ" in args[1]
