# -*- coding: utf-8 -*-
"""Handlers package."""

from bot.handlers.start import start_command, help_command, handle_return_to_menu
from bot.handlers.news import news_command, news_command_internal
from bot.handlers.manage import (
    add_channel_command,
    remove_channel_command,
    remove_all_channels_command,
    list_channels_command,
    time_command,
    posts_command,
    restore_backup_command,
    handle_add_channel_input,
    handle_remove_channel_input,
    handle_time_interval_input,
    handle_news_count_input,
    handle_new_folder_name,
    WAITING_FOR_CHANNEL_ADD,
    WAITING_FOR_CHANNEL_REMOVE,
    WAITING_FOR_TIME_INTERVAL,
    WAITING_FOR_NEWS_COUNT,
    WAITING_FOR_NEW_FOLDER_NAME
)
from bot.handlers.buttons import (
    button_callback,
    handle_add_to_feed_channel,
    handle_add_to_feed_description,
    handle_remove_from_feed_channel,
    handle_remove_from_feed_reason,
    handle_restrict_access_channel,
    handle_restrict_access_reason,
    WAITING_FOR_ADD_TO_FEED_CHANNEL,
    WAITING_FOR_ADD_TO_FEED_HASHTAG,
    WAITING_FOR_ADD_TO_FEED_DESCRIPTION,
    WAITING_FOR_REMOVE_FROM_FEED_CHANNEL,
    WAITING_FOR_REMOVE_FROM_FEED_REASON,
    WAITING_FOR_RESTRICT_ACCESS_CHANNEL,
    WAITING_FOR_RESTRICT_ACCESS_REASON
)

__all__ = [
    'start_command',
    'help_command',
    'handle_return_to_menu',
    'news_command',
    'news_command_internal',
    'add_channel_command',
    'remove_channel_command',
    'remove_all_channels_command',
    'list_channels_command',
    'time_command',
    'posts_command',
    'restore_backup_command',
    'handle_add_channel_input',
    'handle_remove_channel_input',
    'handle_time_interval_input',
    'handle_news_count_input',
    'handle_new_folder_name',
    'button_callback',
    'handle_add_to_feed_channel',
    'handle_add_to_feed_description',
    'handle_remove_from_feed_channel',
    'handle_remove_from_feed_reason',
    'handle_restrict_access_channel',
    'handle_restrict_access_reason',
    'WAITING_FOR_CHANNEL_ADD',
    'WAITING_FOR_CHANNEL_REMOVE',
    'WAITING_FOR_TIME_INTERVAL',
    'WAITING_FOR_NEWS_COUNT',
    'WAITING_FOR_NEW_FOLDER_NAME',
    'WAITING_FOR_ADD_TO_FEED_CHANNEL',
    'WAITING_FOR_ADD_TO_FEED_HASHTAG',
    'WAITING_FOR_ADD_TO_FEED_DESCRIPTION',
    'WAITING_FOR_REMOVE_FROM_FEED_CHANNEL',
    'WAITING_FOR_REMOVE_FROM_FEED_REASON',
    'WAITING_FOR_RESTRICT_ACCESS_CHANNEL',
    'WAITING_FOR_RESTRICT_ACCESS_REASON'
]
