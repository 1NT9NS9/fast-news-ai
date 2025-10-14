# -*- coding: utf-8 -*-
"""Main bot entry point - redirects to modular structure."""
import os
import sys
from pathlib import Path

# Ensure bot package is in path
sys.path.insert(0, str(Path(__file__).parent))

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters

from bot.utils.config import TELEGRAM_BOT_API
from bot.utils.logger import setup_logging

# Import all handlers
from bot.handlers import (
    # Command handlers
    start_command,
    help_command,
    handle_return_to_menu,
    news_command,
    add_channel_command,
    remove_channel_command,
    remove_all_channels_command,
    list_channels_command,
    time_command,
    posts_command,
    restore_backup_command,
    # Conversation handlers
    button_callback,
    handle_add_channel_input,
    handle_remove_channel_input,
    handle_time_interval_input,
    handle_news_count_input,
    handle_new_folder_name,
    handle_add_to_feed_channel,
    handle_add_to_feed_description,
    handle_remove_from_feed_channel,
    handle_remove_from_feed_reason,
    handle_restrict_access_channel,
    handle_restrict_access_reason,
    # States
    WAITING_FOR_CHANNEL_ADD,
    WAITING_FOR_CHANNEL_REMOVE,
    WAITING_FOR_TIME_INTERVAL,
    WAITING_FOR_NEWS_COUNT,
    WAITING_FOR_NEW_FOLDER_NAME,
    WAITING_FOR_ADD_TO_FEED_CHANNEL,
    WAITING_FOR_ADD_TO_FEED_HASHTAG,
    WAITING_FOR_ADD_TO_FEED_DESCRIPTION,
    WAITING_FOR_REMOVE_FROM_FEED_CHANNEL,
    WAITING_FOR_REMOVE_FROM_FEED_REASON,
    WAITING_FOR_RESTRICT_ACCESS_CHANNEL,
    WAITING_FOR_RESTRICT_ACCESS_REASON
)

# Import services for cleanup
from bot.services import ScraperService

# Setup logging
logger, user_logger = setup_logging()


def main():
    """Start the bot."""
    logger.info("Starting bot...")

    # Initialize scraper service for cleanup
    scraper = ScraperService()

    # Create application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_API)
        .post_shutdown(lambda _: scraper.close_http_client())
        .build()
    )

    # Create conversation handler for button interactions
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback)],
        states={
            WAITING_FOR_CHANNEL_ADD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_channel_input)
            ],
            WAITING_FOR_CHANNEL_REMOVE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_channel_input)
            ],
            WAITING_FOR_TIME_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time_interval_input)
            ],
            WAITING_FOR_NEWS_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_news_count_input)
            ],
            WAITING_FOR_ADD_TO_FEED_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_to_feed_channel)
            ],
            WAITING_FOR_ADD_TO_FEED_HASHTAG: [
                CallbackQueryHandler(button_callback)
            ],
            WAITING_FOR_ADD_TO_FEED_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_add_to_feed_description)
            ],
            WAITING_FOR_REMOVE_FROM_FEED_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_from_feed_channel)
            ],
            WAITING_FOR_REMOVE_FROM_FEED_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_remove_from_feed_reason)
            ],
            WAITING_FOR_RESTRICT_ACCESS_CHANNEL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_restrict_access_channel)
            ],
            WAITING_FOR_RESTRICT_ACCESS_REASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_restrict_access_reason)
            ],
            WAITING_FOR_NEW_FOLDER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_new_folder_name)
            ],
        },
        fallbacks=[CommandHandler('start', start_command)],
        allow_reentry=True
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("restore_backup", restore_backup_command))
    application.add_handler(conv_handler)

    # Keep old command handlers for backward compatibility
    application.add_handler(CommandHandler("add", add_channel_command))
    application.add_handler(CommandHandler("remove", remove_channel_command))
    application.add_handler(CommandHandler("remove_all", remove_all_channels_command))
    application.add_handler(CommandHandler("list", list_channels_command))
    application.add_handler(CommandHandler("time", time_command))
    application.add_handler(CommandHandler("posts", posts_command))
    application.add_handler(CommandHandler("news", news_command))

    # Handler for persistent keyboard button
    application.add_handler(MessageHandler(filters.Text(["🏠 Вернуться в меню"]), handle_return_to_menu))

    # Start the bot
    logger.info("Bot started successfully. Running polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
