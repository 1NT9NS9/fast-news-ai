# -*- coding: utf-8 -*-
"""Logging setup for the bot.

Provides two loggers:
- logger: General application logging (bot.log)
- user_logger: User interaction logging (bot_user.log)

Additionally supports Telegram log notifications for ERROR/CRITICAL messages.
"""
import logging
import requests
from typing import Tuple, Optional


class TelegramLogHandler(logging.Handler):
    """Custom logging handler that sends log messages to a Telegram chat.

    Used for sending ERROR and CRITICAL level messages to admin for monitoring.
    """

    def __init__(self, bot_token: str, chat_id: int, level: int = logging.ERROR):
        """Initialize the Telegram log handler.

        Args:
            bot_token: Telegram bot API token
            chat_id: Telegram chat ID to send messages to
            level: Minimum logging level (default: ERROR)
        """
        super().__init__(level)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.session = requests.Session()

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to Telegram chat.

        Args:
            record: Log record to send
        """
        try:
            log_entry = self.format(record)

            # Determine emoji based on log level
            emoji = "🔴" if record.levelno >= logging.ERROR else "⚠️"

            # Format message with level indicator
            message = f"{emoji} {record.levelname}\n\n{log_entry}"

            # Truncate if too long (Telegram message limit is 4096 chars)
            if len(message) > 4000:
                message = message[:3997] + "..."

            # Send message via Telegram API (synchronous to avoid async issues)
            self.session.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=5
            )
        except Exception:
            # Silently fail to avoid breaking the application
            # (logging errors shouldn't crash the bot)
            pass


def setup_logging(bot_token: Optional[str] = None, admin_chat_id: Optional[int] = None) -> Tuple[logging.Logger, logging.Logger]:
    """Setup and configure logging for the bot.

    Args:
        bot_token: Telegram bot token for sending log notifications (optional)
        admin_chat_id: Admin chat ID for receiving log messages (optional)

    Returns:
        Tuple[logging.Logger, logging.Logger]: (logger, user_logger)
            - logger: General application logger
            - user_logger: User interactions logger
    """
    # Configure main logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # Add Telegram handler for ERROR/CRITICAL messages if configured
    if bot_token and admin_chat_id:
        try:
            telegram_handler = TelegramLogHandler(
                bot_token=bot_token,
                chat_id=admin_chat_id,
                level=logging.ERROR
            )
            telegram_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s\n%(message)s')
            )

            # Attach to root logger to catch all ERROR/CRITICAL from any module
            root_logger = logging.getLogger()
            root_logger.addHandler(telegram_handler)

            logger.info(f"Telegram log notifications enabled for chat {admin_chat_id}")
        except Exception as e:
            logger.warning(f"Failed to setup Telegram log handler: {e}")

    # Create separate logger for user interactions
    user_logger = logging.getLogger('user_interactions')
    user_logger.setLevel(logging.INFO)
    user_handler = logging.FileHandler('bot_user.log', encoding='utf-8')
    user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    user_logger.addHandler(user_handler)
    # Prevent propagation to root logger to keep it separate
    user_logger.propagate = False

    return logger, user_logger
