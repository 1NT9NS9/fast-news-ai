# -*- coding: utf-8 -*-
"""Logging setup for the bot with secret redaction and safe formatting."""

from __future__ import annotations

import asyncio
import copy
import logging
import ntpath
import posixpath
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from bot.services import messenger as messenger_service

API_KEY_PATTERN = re.compile(r"AIza[\w-]{35}")
BOT_TOKEN_PATTERN = re.compile(r"\d+:AA[\w-]{33}")
WINDOWS_PATH_PATTERN = re.compile(r"(?<!\S)[A-Za-z]:\\(?:[^\\\s]+\\)+[^\\\s]+")
WINDOWS_FWD_PATH_PATTERN = re.compile(r"(?<!\S)[A-Za-z]:/(?:[^/\s]+/)+[^/\s]+")
POSIX_PATH_PATTERN = re.compile(r"(?<!\S)/(?:[^/\s]+/)+[^/\s]+")
TELEGRAM_MESSAGE_LIMIT = 4000
_ROOT_LOGGING_INITIALIZED = False
_USER_LOGGER_INITIALIZED = False
_TELEGRAM_HANDLER: "TelegramLogHandler | None" = None
_TELEGRAM_CHAT_ID: Optional[int] = None


def _redact_secrets(text: str) -> str:
    """Replace known secret patterns with redaction tokens."""
    sanitized = API_KEY_PATTERN.sub("[REDACTED_API_KEY]", text)
    sanitized = BOT_TOKEN_PATTERN.sub("[REDACTED_BOT_TOKEN]", sanitized)
    return sanitized


def _strip_absolute_paths(text: str) -> str:
    """Collapse absolute paths to basenames to avoid leaking filesystem layout."""

    def _windows_replacer(match: re.Match[str]) -> str:
        path = match.group(0)
        basename = ntpath.basename(path)
        return basename or path

    def _posix_replacer(match: re.Match[str]) -> str:
        path = match.group(0)
        basename = posixpath.basename(path)
        return basename or path

    sanitized = WINDOWS_PATH_PATTERN.sub(_windows_replacer, text)
    sanitized = WINDOWS_FWD_PATH_PATTERN.sub(_windows_replacer, sanitized)
    sanitized = POSIX_PATH_PATTERN.sub(_posix_replacer, sanitized)
    return sanitized


def _sanitize_text(value: str) -> str:
    """Apply redaction and path stripping to log text."""
    sanitized = _redact_secrets(value)
    sanitized = _strip_absolute_paths(sanitized)
    return sanitized


def _sanitize_arg(value: object) -> object:
    """Sanitize logging argument values while preserving numeric types."""
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, (int, float, complex)):
        return value
    sanitized = _sanitize_text(str(value))
    return sanitized


class SafeFormatter(logging.Formatter):
    """Formatter that redacts secrets and strips absolute paths."""

    def format(self, record: logging.LogRecord) -> str:
        record_copy = copy.copy(record)

        if record_copy.args:
            if isinstance(record_copy.args, Mapping):
                record_copy.args = {
                    key: _sanitize_arg(value)
                    for key, value in record_copy.args.items()
                }
            elif isinstance(record_copy.args, Sequence) and not isinstance(
                record_copy.args, (str, bytes, bytearray)
            ):
                record_copy.args = tuple(
                    _sanitize_arg(arg) for arg in record_copy.args
                )
            elif isinstance(record_copy.args, str):
                record_copy.args = (_sanitize_text(record_copy.args),)

        if isinstance(record_copy.msg, str):
            record_copy.msg = _sanitize_text(record_copy.msg)
        else:
            record_copy.msg = _sanitize_text(str(record_copy.msg))
            record_copy.args = None

        if record_copy.pathname:
            record_copy.pathname = Path(record_copy.pathname).name

        if record_copy.stack_info:
            record_copy.stack_info = _sanitize_text(str(record_copy.stack_info))

        if record_copy.exc_info:
            record_copy.exc_text = self.formatException(record_copy.exc_info)
        elif record_copy.exc_text:
            record_copy.exc_text = _sanitize_text(record_copy.exc_text)

        return super().format(record_copy)

    def formatException(self, ei):  # type: ignore[override]
        formatted = super().formatException(ei)
        return _sanitize_text(formatted)


class TelegramLogHandler(logging.Handler):
    """Logging handler that routes error notifications through the messenger service."""

    def __init__(self, chat_id: int, level: int = logging.ERROR):
        super().__init__(level)
        self.chat_id = chat_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            from bot.services import messenger as messenger_service  # Lazy import to avoid circular deps
        except ImportError:
            return

        if not messenger_service.is_configured():
            return

        try:
            payload = self.format(record)
            header = "[ERROR]" if record.levelno >= logging.ERROR else "[WARN]"
            message = f"{header} {record.levelname}\n\n{payload}"
            if len(message) > TELEGRAM_MESSAGE_LIMIT:
                message = f"{message[:TELEGRAM_MESSAGE_LIMIT - 3]}..."

            async def _send() -> None:
                try:
                    await messenger_service.send_text(chat_id=self.chat_id, text=message)
                except Exception:
                    # Avoid infinite logging loops on notification failures.
                    pass

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.create_task(_send())
            else:
                asyncio.run(_send())
        except Exception:
            self.handleError(record)


def setup_logging(bot_token: Optional[str] = None, admin_chat_id: Optional[int] = None) -> Tuple[logging.Logger, logging.Logger]:
    """Setup and configure logging for the bot.

    Args:
        bot_token: Unused placeholder for backward compatibility (kept to retain signature).
        admin_chat_id: Admin chat ID for receiving log messages (optional)

    Returns:
        Tuple[logging.Logger, logging.Logger]: (logger, user_logger)
            - logger: General application logger
            - user_logger: User interactions logger
    """
    global _ROOT_LOGGING_INITIALIZED, _USER_LOGGER_INITIALIZED, _TELEGRAM_HANDLER, _TELEGRAM_CHAT_ID

    root_logger = logging.getLogger()

    if not _ROOT_LOGGING_INITIALIZED:
        file_formatter = SafeFormatter("%(asctime)s - %(levelname)s - %(message)s")
        console_formatter = SafeFormatter("%(levelname)s - %(message)s")

        file_handler = logging.FileHandler("bot.log", encoding="utf-8")
        file_handler.setFormatter(file_formatter)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(console_formatter)

        root_logger.setLevel(logging.INFO)
        root_logger.handlers.clear()
        root_logger.addHandler(file_handler)
        root_logger.addHandler(stream_handler)
        _ROOT_LOGGING_INITIALIZED = True

    logger = logging.getLogger("bot")

    # Add or update Telegram handler for ERROR/CRITICAL messages if configured
    if admin_chat_id and (_TELEGRAM_CHAT_ID != admin_chat_id):
        if _TELEGRAM_HANDLER:
            root_logger.removeHandler(_TELEGRAM_HANDLER)

        telegram_handler = TelegramLogHandler(
            chat_id=admin_chat_id,
            level=logging.ERROR,
        )
        telegram_handler.setFormatter(
            SafeFormatter("%(asctime)s - %(name)s\n%(message)s")
        )
        root_logger.addHandler(telegram_handler)
        _TELEGRAM_HANDLER = telegram_handler
        _TELEGRAM_CHAT_ID = admin_chat_id
        logger.info(f"Telegram log notifications configured for chat {admin_chat_id}")

    # Create separate logger for user interactions once
    user_logger = logging.getLogger("user_interactions")
    if not _USER_LOGGER_INITIALIZED:
        user_logger.setLevel(logging.INFO)
        user_logger.handlers.clear()
        user_handler = logging.FileHandler("bot_user.log", encoding="utf-8")
        user_handler.setFormatter(SafeFormatter("%(asctime)s - %(message)s"))
        user_logger.addHandler(user_handler)
        user_logger.propagate = False
        _USER_LOGGER_INITIALIZED = True

    return logger, user_logger
