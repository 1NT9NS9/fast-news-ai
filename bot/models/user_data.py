# -*- coding: utf-8 -*-
"""Data models and validation for user data.

Contains user data structures, validation logic, and migration functions.
"""
import re
from typing import Dict, List, Tuple
from bot.utils.config import MAX_NEWS_TIME_LIMIT_HOURS, MAX_SUMMARY_POSTS_LIMIT


def migrate_user_data_to_folders(data: dict) -> dict:
    """Migrate old user data format to new folder-based format.

    Args:
        data: User data dictionary

    Returns:
        Migrated user data dictionary
    """
    for user_id, user_info in data.items():
        # Check if user already has folders structure
        if 'folders' not in user_info:
            # Migrate old 'channels' list to folders
            old_channels = user_info.get('channels', [])
            user_info['folders'] = {
                'Папка1': old_channels
            }
            # Set Папка1 as active
            user_info['active_folder'] = 'Папка1'
            # Keep 'channels' for backward compatibility but it won't be used
    return data


def validate_user_data(data: dict) -> Tuple[bool, List[str]]:
    """Validate the integrity of the user data structure.

    Args:
        data: User data dictionary to validate

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    if data is None:
        errors.append('User data is None')
        return False, errors

    if not isinstance(data, dict):
        errors.append('User data root must be a dictionary')
        return False, errors

    for user_id, user_info in data.items():
        if not isinstance(user_id, str):
            errors.append(f'User key {user_id!r} must be a string.')
            continue

        if not isinstance(user_info, dict):
            errors.append(f'User {user_id}: entry must be a dictionary.')
            continue

        folders = user_info.get('folders')
        if not isinstance(folders, dict):
            errors.append(f'User {user_id}: "folders" must be a dictionary.')
        else:
            for folder_name, channels in folders.items():
                if not isinstance(folder_name, str):
                    errors.append(f'User {user_id}: folder name {folder_name!r} must be a string.')
                    continue
                if not isinstance(channels, list):
                    errors.append(f'User {user_id}: folder {folder_name!r} must contain a list of channels.')
                    continue
                for channel in channels:
                    if not isinstance(channel, str):
                        errors.append(f'User {user_id}: channel entries in folder {folder_name!r} must be strings.')
                    elif not channel.startswith('@'):
                        errors.append(f'User {user_id}: channel {channel!r} must start with "@".')

        active_folder = user_info.get('active_folder')
        if active_folder is None:
            errors.append(f'User {user_id}: missing "active_folder".')
        elif not isinstance(active_folder, str):
            errors.append(f'User {user_id}: "active_folder" must be a string.')
        elif isinstance(folders, dict) and folders and active_folder not in folders:
            errors.append(f'User {user_id}: "active_folder" {active_folder!r} not found in folders.')

        time_limit = user_info.get('time_limit')
        if time_limit is not None:
            if not isinstance(time_limit, int):
                errors.append(f'User {user_id}: "time_limit" must be an integer.')
            elif time_limit <= 0 or time_limit > MAX_NEWS_TIME_LIMIT_HOURS:
                errors.append(f'User {user_id}: "time_limit" {time_limit!r} out of allowed range.')

        max_posts = user_info.get('max_posts')
        if max_posts is not None:
            if not isinstance(max_posts, int):
                errors.append(f'User {user_id}: "max_posts" must be an integer.')
            elif max_posts <= 0 or max_posts > MAX_SUMMARY_POSTS_LIMIT:
                errors.append(f'User {user_id}: "max_posts" {max_posts!r} out of allowed range.')

        news_requests = user_info.get('news_requests')
        if news_requests is not None:
            if not isinstance(news_requests, dict):
                errors.append(f'User {user_id}: "news_requests" must be a dictionary.')
            else:
                for date_key, count in news_requests.items():
                    if not isinstance(date_key, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_key):
                        errors.append(f'User {user_id}: invalid news_requests date key {date_key!r}.')
                    if not isinstance(count, int) or count < 0:
                        errors.append(f'User {user_id}: invalid news_requests count {count!r} for {date_key!r}.')

    return len(errors) == 0, errors
