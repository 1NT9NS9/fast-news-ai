# -*- coding: utf-8 -*-
"""Messenger helpers that funnel outbound sends through the rate limiter queue."""

from __future__ import annotations

import asyncio
from typing import Any, Sequence

from telegram import Bot, InputMedia

try:
    from bot.services.rate_limiter import RateLimiter
except ImportError:  # pragma: no cover
    RateLimiter = None  # type: ignore

_rate_limiter: "RateLimiter | None" = None
_bot: Bot | None = None


def configure(*, bot: Bot, rate_limiter: "RateLimiter | None") -> None:
    """Register the global bot and optional rate limiter instances."""
    if bot is None:
        raise ValueError("Messenger.configure requires a Bot instance.")
    global _bot, _rate_limiter
    _bot = bot
    _rate_limiter = rate_limiter


def _require_components() -> tuple[Bot, "RateLimiter | None"]:
    if _bot is None:
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
    kwargs = dict(kwargs)
    if limiter is None:
        return await bot.send_message(chat_id=chat_id, text=text, **kwargs)
    result = await limiter.enqueue_send(
        bot.send_message,
        chat_id=chat_id,
        args=(chat_id, text),
        kwargs=kwargs,
        context=context,
    )
    if isinstance(result, asyncio.Future):
        return await result
    return result


async def send_photo(
    chat_id: int | str,
    photo: Any,
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a photo message for delivery."""
    bot, limiter = _require_components()
    kwargs = dict(kwargs)
    if limiter is None:
        return await bot.send_photo(chat_id=chat_id, photo=photo, **kwargs)
    result = await limiter.enqueue_send(
        bot.send_photo,
        chat_id=chat_id,
        args=(chat_id, photo),
        kwargs=kwargs,
        context=context,
    )
    if isinstance(result, asyncio.Future):
        return await result
    return result


async def send_document(
    chat_id: int | str,
    document: Any,
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a document for delivery."""
    bot, limiter = _require_components()
    kwargs = dict(kwargs)
    if limiter is None:
        return await bot.send_document(chat_id=chat_id, document=document, **kwargs)
    result = await limiter.enqueue_send(
        bot.send_document,
        chat_id=chat_id,
        args=(chat_id, document),
        kwargs=kwargs,
        context=context,
    )
    if isinstance(result, asyncio.Future):
        return await result
    return result


async def send_media_group(
    chat_id: int | str,
    media: Sequence[InputMedia],
    *,
    context: Any = None,
    **kwargs: Any,
) -> Any:
    """Queue a media group for delivery."""
    bot, limiter = _require_components()
    kwargs = dict(kwargs)
    if limiter is None:
        return await bot.send_media_group(chat_id=chat_id, media=list(media), **kwargs)
    result = await limiter.enqueue_send(
        bot.send_media_group,
        chat_id=chat_id,
        args=(chat_id, list(media)),
        kwargs=kwargs,
        context=context,
    )
    if isinstance(result, asyncio.Future):
        return await result
    return result


def is_configured() -> bool:
    """Return True when messenger helpers are ready for use."""
    return _bot is not None


async def get_queue_metrics() -> dict[str, Any]:
    """Expose the rate limiter queue metrics for diagnostics."""
    _, limiter = _require_components()
    if limiter is None:
        return {
            "queue_depth": 0,
            "max_delay_sec": 0.0,
            "avg_delay_sec": 0.0,
            "max_delay_chat_id": None,
            "max_delay_chat_sec": 0.0,
            "sampled_at": asyncio.get_running_loop().time(),
        }
    return await limiter.queue_metrics()


__all__ = [
    "configure",
    "is_configured",
    "send_text",
    "send_photo",
    "send_document",
    "send_media_group",
    "get_queue_metrics",
]
