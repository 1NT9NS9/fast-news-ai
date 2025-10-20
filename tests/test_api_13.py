# -*- coding: utf-8 -*-
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.ext import ConversationHandler

sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.handlers.buttons import button_callback
from bot.services import messenger as messenger_service


@pytest.mark.asyncio
async def test_api_13_button_callback_uses_messenger(monkeypatch):
    """Ensure button callback routes outbound messages through messenger service."""
    send_mock = AsyncMock(return_value=SimpleNamespace())
    monkeypatch.setattr(messenger_service, "send_text", send_mock)

    async def fail_reply_text(*args, **kwargs):
        raise AssertionError("reply_text should not be used when rate limiter is enabled")

    dummy_message = SimpleNamespace(reply_text=fail_reply_text)

    class DummyQuery:
        data = "return_to_menu"

        def __init__(self):
            self.message = dummy_message
            self.answered = False

        async def answer(self):
            self.answered = True

    update = SimpleNamespace(
        callback_query=DummyQuery(),
        effective_user=SimpleNamespace(id=42, username="tester"),
        effective_chat=SimpleNamespace(id=99),
    )
    context = SimpleNamespace()

    result = await button_callback(update, context)

    assert result == ConversationHandler.END
    assert update.callback_query.answered is True
    send_mock.assert_awaited_once()
    args, kwargs = send_mock.await_args
    assert args[0] == 99
    assert "меню" in args[1]
    assert "reply_markup" in kwargs
