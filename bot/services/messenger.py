# -*- coding: utf-8 -*-
"""Messenger helpers that funnel outbound sends through the rate limiter queue."""

from __future__ import annotations

from typing import Any, Sequence

from telegram import Bot, InputMedia

from bot.services.rate_limiter import RateLimiter

_rate_limiter: RateLimiter | None = None
_bot: Bot | None = None


def configure(*, bot: Bot, rate_limiter: RateLimiter) -> None:
    """Register the global bot and rate limiter instances used by helper wrappers."""
    if bot is None:
        raise ValueError("Messenger.configure requires a Bot instance.")
    if rate_limiter is None:
        raise ValueError("Messenger.configure requires a RateLimiter instance.")
    global _bot, _rate_limiter
    _bot = bot
    _rate_limiter = rate_limiter


def _require_components() -> tuple[Bot, RateLimiter]:
    if _bot is None or _rate_limiter is None:
        raise RuntimeError("Messenger not configured. Call configure() during startup.")
    return _bot, _rate_limiter


async def send_text(
    chat_id: int | str,
    text: str,
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a text message for delivery."""
    bot, limiter = _require_components()
    return await limiter.enqueue_send(
        bot.send_message,
        chat_id=chat_id,
        args=(chat_id, text),
        kwargs=dict(kwargs),
        context=context,
    )


async def send_photo(
    chat_id: int | str,
    photo: Any,
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a photo message for delivery."""
    bot, limiter = _require_components()
    return await limiter.enqueue_send(
        bot.send_photo,
        chat_id=chat_id,
        args=(chat_id, photo),
        kwargs=dict(kwargs),
        context=context,
    )


async def send_document(
    chat_id: int | str,
    document: Any,
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a document for delivery."""
    bot, limiter = _require_components()
    return await limiter.enqueue_send(
        bot.send_document,
        chat_id=chat_id,
        args=(chat_id, document),
        kwargs=dict(kwargs),
        context=context,
    )


async def send_media_group(
    chat_id: int | str,
    media: Sequence[InputMedia],
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a media group for delivery."""
    bot, limiter = _require_components()
    return await limiter.enqueue_send(
        bot.send_media_group,
        chat_id=chat_id,
        args=(chat_id, list(media)),
        kwargs=dict(kwargs),
        context=context,
    )


def is_configured() -> bool:
    """Return True when messenger helpers are ready for use."""
    return _bot is not None and _rate_limiter is not None


__all__ = [
    "configure",
    "is_configured",
    "send_text",
    "send_photo",
    "send_document",
    "send_media_group",
]
