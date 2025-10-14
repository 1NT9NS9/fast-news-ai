# -*- coding: utf-8 -*-
import os
import shutil

# Suppress gRPC warnings - must be set BEFORE importing google libraries
os.environ['GRPC_VERBOSITY'] = 'NONE'
os.environ['GLOG_minloglevel'] = '2'
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'

import json
import asyncio
import aiofiles
import re
from collections import defaultdict
from typing import Optional
from datetime import datetime, timedelta, timezone
import httpx
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from dotenv import load_dotenv
import google.generativeai as genai
from sklearn.cluster import DBSCAN
import numpy as np
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Create separate logger for user interactions
user_logger = logging.getLogger('user_interactions')
user_logger.setLevel(logging.INFO)
user_handler = logging.FileHandler('bot_user.log', encoding='utf-8')
user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
user_logger.addHandler(user_handler)
# Prevent propagation to root logger to keep it separate
user_logger.propagate = False

TELEGRAM_BOT_API = os.getenv('TELEGRAM_BOT_API')
GEMINI_API = os.getenv('GEMINI_API')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')  # Admin's Telegram chat ID for receiving forms
USER_DATA_FILE = 'user_data.json'
CHANNEL_FEED_FILE = 'channel_feed.json'
USER_DATA_BACKUP_DIR = os.path.join('backups', 'user_data')
MAX_BACKUP_COUNT = 20
BACKUP_RETENTION_DAYS = 7
try:
    ADMIN_CHAT_ID_INT = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None
except ValueError:
    logger.error('ADMIN_CHAT_ID must be an integer value')
    ADMIN_CHAT_ID_INT = None

MAX_CHANNELS = 10
SIMILARITY_THRESHOLD = 0.9
MAX_POSTS_PER_CHANNEL = 20
DEFAULT_NEWS_TIME_LIMIT_HOURS = 24  # Default time range for news
MAX_NEWS_TIME_LIMIT_HOURS = 720  # Maximum allowed time range (30 days)
DEFAULT_MAX_SUMMARY_POSTS = 10  # Default number of news summaries
MAX_SUMMARY_POSTS_LIMIT = 30  # Maximum allowed summaries
MAX_NEWS_REQUESTS_PER_DAY = 5  # Rate limit for /news command
GEMINI_API_RATE_LIMIT = 4000  # Gemini API rate limit: 4000 requests per minute
GEMINI_CONCURRENT_LIMIT = 4000  # Max concurrent Gemini API requests

# Configure Google Generative AI
genai.configure(api_key=GEMINI_API)

# In-memory cache for user data to reduce file I/O
_user_data_cache = None
_cache_lock = asyncio.Lock()
_user_channels_cache = {}
_user_channels_cache_lock = asyncio.Lock()

# Backup debouncing - track last backup time to avoid excessive backups
_last_backup_time = 0
_backup_debounce_seconds = 60  # Max 1 backup per minute

# Semaphore for Gemini API rate limiting
_gemini_semaphore = asyncio.Semaphore(GEMINI_CONCURRENT_LIMIT)

# Cached Gemini model instance
_gemini_model = None


_http_client: Optional[httpx.AsyncClient] = None
_http_client_lock = asyncio.Lock()


async def get_http_client() -> httpx.AsyncClient:
    """Return a shared HTTP client with connection pooling."""
    global _http_client
    if _http_client is None:
        async with _http_client_lock:
            if _http_client is None:
                _http_client = httpx.AsyncClient(follow_redirects=True, timeout=30.0)
    return _http_client


async def close_http_client(*_) -> None:
    """Close the shared HTTP client if it was created."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None

# Conversation states for user input handling
WAITING_FOR_CHANNEL_ADD = 1
WAITING_FOR_CHANNEL_REMOVE = 2
WAITING_FOR_TIME_INTERVAL = 3
WAITING_FOR_NEWS_COUNT = 4
# Channel owner form states
WAITING_FOR_ADD_TO_FEED_CHANNEL = 5
WAITING_FOR_ADD_TO_FEED_HASHTAG = 6
WAITING_FOR_ADD_TO_FEED_DESCRIPTION = 7
WAITING_FOR_REMOVE_FROM_FEED_CHANNEL = 8
WAITING_FOR_REMOVE_FROM_FEED_REASON = 9
WAITING_FOR_RESTRICT_ACCESS_CHANNEL = 10
WAITING_FOR_RESTRICT_ACCESS_REASON = 11
# Folder management states
WAITING_FOR_NEW_FOLDER_NAME = 12


def _cleanup_old_backups():
    """Remove backups exceeding retention or rotation limits."""
    try:
        entries = os.listdir(USER_DATA_BACKUP_DIR)
    except FileNotFoundError:
        return

    cutoff = datetime.utcnow() - timedelta(days=BACKUP_RETENTION_DAYS)
    backups = []
    for entry in entries:
        if not entry.startswith('user_data_') or not entry.endswith('.json'):
            continue
        path = os.path.join(USER_DATA_BACKUP_DIR, entry)
        try:
            stat_result = os.stat(path)
        except OSError as exc:
            logger.warning('Failed to stat backup %s: %s', path, exc)
            continue
        backups.append((path, stat_result.st_mtime))

    backups.sort(key=lambda item: item[1], reverse=True)

    kept_backups = []
    for path, mtime in backups:
        backup_time = datetime.utcfromtimestamp(mtime)
        if backup_time < cutoff:
            try:
                os.remove(path)
            except OSError as exc:
                logger.warning('Failed to remove expired backup %s: %s', path, exc)
            continue
        kept_backups.append((path, mtime))

    for path, _ in kept_backups[MAX_BACKUP_COUNT:]:
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning('Failed to remove rotated backup %s: %s', path, exc)


def _perform_user_data_backup():
    """Create a timestamped backup of the user data file."""
    if not os.path.exists(USER_DATA_FILE):
        return

    try:
        os.makedirs(USER_DATA_BACKUP_DIR, exist_ok=True)
    except OSError as exc:
        logger.warning('Failed to ensure backup directory %s: %s', USER_DATA_BACKUP_DIR, exc)
        return

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'user_data_{timestamp}.json'
    backup_path = os.path.join(USER_DATA_BACKUP_DIR, backup_filename)

    try:
        shutil.copy2(USER_DATA_FILE, backup_path)
    except OSError as exc:
        logger.warning('Failed to create user data backup: %s', exc)
        return

    _cleanup_old_backups()


async def backup_user_data():
    """Asynchronously back up the current user data state with debouncing."""
    global _last_backup_time

    current_time = datetime.now().timestamp()
    time_since_last_backup = current_time - _last_backup_time

    # Skip backup if less than debounce period has passed
    if time_since_last_backup < _backup_debounce_seconds:
        logger.debug(f"Skipping backup (last backup {time_since_last_backup:.1f}s ago, debounce: {_backup_debounce_seconds}s)")
        return

    # Update last backup time and perform backup
    _last_backup_time = current_time
    await asyncio.to_thread(_perform_user_data_backup)


def list_user_data_backups():
    """Return sorted metadata for existing user data backups."""
    try:
        entries = os.listdir(USER_DATA_BACKUP_DIR)
    except FileNotFoundError:
        return []

    backups = []
    for entry in entries:
        if not entry.startswith('user_data_') or not entry.endswith('.json'):
            continue
        path = os.path.join(USER_DATA_BACKUP_DIR, entry)
        try:
            stat_result = os.stat(path)
        except OSError as exc:
            logger.warning('Failed to stat backup %s: %s', path, exc)
            continue
        backups.append({'path': path, 'name': entry, 'mtime': stat_result.st_mtime})

    backups.sort(key=lambda item: item['mtime'], reverse=True)
    return backups


async def _invalidate_user_channel_cache(user_id=None):
    '''Clear cached channel lists either globally or for a specific user.'''
    async with _user_channels_cache_lock:
        if user_id is None:
            _user_channels_cache.clear()
        else:
            _user_channels_cache.pop(str(user_id), None)


async def _cache_user_channels(user_id_str, channels):
    '''Store a snapshot of a user's channels for quick reuse.'''
    async with _user_channels_cache_lock:
        _user_channels_cache[user_id_str] = tuple(channels)


def _extract_all_channels(user_data):
    '''Return a deduplicated list of all channels from the user data.'''
    if not user_data:
        return []
    folders = user_data.get('folders')
    if isinstance(folders, dict):
        return list(dict.fromkeys(
            channel
            for channels in folders.values()
            for channel in channels
        ))
    return list(dict.fromkeys(user_data.get('channels', [])))



async def restore_user_data_from_backup(backup_path):
    """Restore user data from a selected backup file."""
    global _user_data_cache

    async with _cache_lock:
        await backup_user_data()
        try:
            async with aiofiles.open(backup_path, 'r', encoding='utf-8') as src:
                raw_content = await src.read()
        except FileNotFoundError as exc:
            raise FileNotFoundError(f'Backup file not found: {backup_path}') from exc
        except OSError as exc:
            raise OSError(f'Failed to read backup {backup_path}: {exc}') from exc

        try:
            restored_data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise ValueError(f'Backup file is not valid JSON: {backup_path}') from exc

        restored_data = migrate_user_data_to_folders(restored_data)

        try:
            async with aiofiles.open(USER_DATA_FILE, 'w', encoding='utf-8') as dst:
                await dst.write(json.dumps(restored_data, indent=2, ensure_ascii=False))
        except OSError as exc:
            raise OSError(f'Failed to write restored data: {exc}') from exc

        _user_data_cache = restored_data
        await _invalidate_user_channel_cache()

    logger.info('User data restored from backup %s', backup_path)
    return restored_data


def migrate_user_data_to_folders(data):
    """Migrate old user data format to new folder-based format."""
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


def validate_user_data(data):
    """Validate the integrity of the user data structure."""
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



async def _attempt_auto_restore_user_data(reason):
    """Attempt to auto-restore user data from the newest valid backup."""
    backups = list_user_data_backups()
    if not backups:
        logger.error('Unable to auto-restore user data (%s): no backups found.', reason)
        return None

    await backup_user_data()

    for backup in backups:
        path = backup['path']
        name = backup['name']
        try:
            async with aiofiles.open(path, 'r', encoding='utf-8') as src:
                raw_content = await src.read()
            candidate = json.loads(raw_content)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning('Skipping backup %s due to read error: %s', name, exc)
            continue

        candidate = migrate_user_data_to_folders(candidate)
        is_valid, issues = validate_user_data(candidate)
        if not is_valid:
            logger.warning('Skipping backup %s due to validation errors: %s', name, '; '.join(issues))
            continue

        try:
            async with aiofiles.open(USER_DATA_FILE, 'w', encoding='utf-8') as dst:
                await dst.write(json.dumps(candidate, indent=2, ensure_ascii=False))
        except OSError as exc:
            logger.error('Failed to write restored user data from %s: %s', name, exc)
            return None

        logger.warning('Auto-restored user data from backup %s after %s.', name, reason)
        return candidate

    logger.error('Unable to auto-restore user data (%s): no valid backups available.', reason)
    return None



async def load_user_data():
    """Load user data from JSON file with validation and auto-recovery."""
    global _user_data_cache

    async with _cache_lock:
        if _user_data_cache is not None:
            return _user_data_cache

        try:
            async with aiofiles.open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                raw_content = await f.read()
        except FileNotFoundError:
            _user_data_cache = {}
            await _invalidate_user_channel_cache()
            return _user_data_cache
        except OSError as exc:
            logger.error('Failed to read %s: %s', USER_DATA_FILE, exc)
            _user_data_cache = {}
            await _invalidate_user_channel_cache()
            return _user_data_cache

        try:
            raw_data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            logger.error('Failed to parse %s: %s', USER_DATA_FILE, exc)
            restored = await _attempt_auto_restore_user_data('JSON decode error')
            if restored is not None:
                _user_data_cache = restored
                await _invalidate_user_channel_cache()
                return restored
            _user_data_cache = {}
            await _invalidate_user_channel_cache()
            return _user_data_cache

        data = migrate_user_data_to_folders(raw_data)
        is_valid, issues = validate_user_data(data)
        if is_valid:
            _user_data_cache = data
            await _invalidate_user_channel_cache()
            return data

        logger.error('User data validation failed: %s', '; '.join(issues))
        restored = await _attempt_auto_restore_user_data('validation failure')
        if restored is not None:
            _user_data_cache = restored
            await _invalidate_user_channel_cache()
            return restored

        _user_data_cache = {}
        await _invalidate_user_channel_cache()
        return _user_data_cache



async def save_user_data(data):
    """Save user data to JSON file and update cache after validation."""
    global _user_data_cache

    async with _cache_lock:
        is_valid, issues = validate_user_data(data)
        if not is_valid:
            logger.error('Aborting save_user_data due to validation errors: %s', '; '.join(issues))
            raise ValueError('User data failed validation; see logs for details.')

        # Trigger backup in background (non-blocking, fire-and-forget)
        if os.path.exists(USER_DATA_FILE):
            asyncio.create_task(backup_user_data())

        _user_data_cache = data
        serialized = json.dumps(data, indent=2, ensure_ascii=False)
        async with aiofiles.open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
            await f.write(serialized)


async def get_user_channels(user_id):
    """Get channels for a specific user from their active folder."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        user_data = data[user_id_str]
        # Check if user has folder structure
        if 'folders' in user_data and 'active_folder' in user_data:
            active_folder = user_data['active_folder']
            folders = user_data['folders']
            return folders.get(active_folder, [])
        # Fallback to old structure
        return user_data.get('channels', [])
    return []


async def get_active_folder_name(user_id):
    """Get the name of the user's active folder."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        user_data = data[user_id_str]
        if 'active_folder' in user_data:
            return user_data['active_folder']
    return 'Папка1'


async def get_all_user_channels(user_id):
    """Return all channels across folders for a user, cached for reuse."""
    user_id_str = str(user_id)

    async with _user_channels_cache_lock:
        cached = _user_channels_cache.get(user_id_str)
    if cached is not None:
        return list(cached)

    data = await load_user_data()
    user_data = data.get(user_id_str)
    channels = _extract_all_channels(user_data)

    await _cache_user_channels(user_id_str, channels)
    return channels


async def set_user_channels(user_id, channels):
    """Set channels for a specific user in their active folder."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'folders': {'Папка1': []},
            'active_folder': 'Папка1'
        }

    user_data = data[user_id_str]
    # Update channels in active folder
    if 'folders' in user_data and 'active_folder' in user_data:
        active_folder = user_data['active_folder']
        user_data['folders'][active_folder] = channels
    else:
        # Fallback to old structure
        user_data['channels'] = channels

    await save_user_data(data)

    all_channels = _extract_all_channels(user_data)
    await _cache_user_channels(user_id_str, all_channels)


async def get_user_time_limit(user_id):
    """Get news time limit for a specific user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        return data[user_id_str].get('time_limit', DEFAULT_NEWS_TIME_LIMIT_HOURS)
    return DEFAULT_NEWS_TIME_LIMIT_HOURS


async def set_user_time_limit(user_id, hours):
    """Set news time limit for a specific user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {}
    data[user_id_str]['time_limit'] = hours
    await save_user_data(data)


async def get_user_max_posts(user_id):
    """Get max posts limit for a specific user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in data:
        return data[user_id_str].get('max_posts', DEFAULT_MAX_SUMMARY_POSTS)
    return DEFAULT_MAX_SUMMARY_POSTS


async def set_user_max_posts(user_id, max_posts):
    """Set max posts limit for a specific user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {}
    data[user_id_str]['max_posts'] = max_posts
    await save_user_data(data)


async def get_user_folders(user_id):
    """Get all folders for a user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str in data and 'folders' in data[user_id_str]:
        return data[user_id_str]['folders']
    return {'Папка1': []}


async def create_folder(user_id, folder_name):
    """Create a new folder for a user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'folders': {},
            'active_folder': 'Папка1'
        }
    if 'folders' not in data[user_id_str]:
        data[user_id_str]['folders'] = {}

    # Check if folder already exists
    if folder_name in data[user_id_str]['folders']:
        return False

    data[user_id_str]['folders'][folder_name] = []
    await save_user_data(data)
    await _cache_user_channels(user_id_str, _extract_all_channels(data[user_id_str]))
    return True


async def delete_folder(user_id, folder_name):
    """Delete a folder (and its channels) for a user."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data or 'folders' not in data[user_id_str]:
        return False

    folders = data[user_id_str]['folders']
    if folder_name not in folders:
        return False

    # Don't allow deleting Папка1 if it's the only folder
    if folder_name == 'Папка1' and len(folders) == 1:
        return False

    del folders[folder_name]

    # If active folder was deleted, switch to Папка1 or first available
    if data[user_id_str].get('active_folder') == folder_name:
        if 'Папка1' in folders:
            data[user_id_str]['active_folder'] = 'Папка1'
        else:
            data[user_id_str]['active_folder'] = list(folders.keys())[0] if folders else 'Папка1'

    await save_user_data(data)
    await _cache_user_channels(user_id_str, _extract_all_channels(data[user_id_str]))
    return True


async def switch_active_folder(user_id, folder_name):
    """Switch the user's active folder."""
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data or 'folders' not in data[user_id_str]:
        return False

    if folder_name not in data[user_id_str]['folders']:
        return False

    data[user_id_str]['active_folder'] = folder_name
    await save_user_data(data)
    return True


async def check_news_rate_limit(user_id):
    """
    Check if user has exceeded daily news request limit.

    Returns:
        tuple: (bool, int) - (is_allowed, remaining_requests)
    """
    data = await load_user_data()
    user_id_str = str(user_id)

    if user_id_str not in data:
        data[user_id_str] = {}

    user_data = data[user_id_str]
    today = datetime.now(timezone.utc).date().isoformat()

    # Check if we need to reset the counter (new day)
    last_request_date = user_data.get('last_news_date')
    if last_request_date != today:
        user_data['news_request_count'] = 0
        user_data['last_news_date'] = today
        await save_user_data(data)

    request_count = user_data.get('news_request_count', 0)
    remaining = MAX_NEWS_REQUESTS_PER_DAY - request_count

    return (request_count < MAX_NEWS_REQUESTS_PER_DAY, remaining)


async def increment_news_request(user_id):
    """Increment the news request counter for a user."""
    data = await load_user_data()
    user_id_str = str(user_id)

    if user_id_str not in data:
        data[user_id_str] = {}

    user_data = data[user_id_str]
    today = datetime.now(timezone.utc).date().isoformat()

    # Ensure we're tracking the right day
    if user_data.get('last_news_date') != today:
        user_data['news_request_count'] = 0
        user_data['last_news_date'] = today

    user_data['news_request_count'] = user_data.get('news_request_count', 0) + 1
    await save_user_data(data)



async def load_channel_feed():
    """Load channel feed data from JSON file."""
    try:
        async with aiofiles.open(CHANNEL_FEED_FILE, 'r', encoding='utf-8') as f:
            content = await f.read()
    except FileNotFoundError:
        return {}
    except OSError:
        return {}

    if not content:
        return {}

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {}



async def save_channel_feed(data):
    """Save channel feed data to JSON file."""
    serialized = json.dumps(data, indent=2, ensure_ascii=False)
    async with aiofiles.open(CHANNEL_FEED_FILE, 'w', encoding='utf-8') as f:
        await f.write(serialized)



async def check_channel_in_feed(channel_name):
    """Check if a channel is in the feed."""
    feed_data = await load_channel_feed()
    return channel_name in feed_data


def create_persistent_keyboard():
    """Create the persistent keyboard with a single 'Return to menu' button."""
    keyboard = [
        [KeyboardButton("🏠 Вернуться в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def create_main_menu():
    """Create the main menu keyboard with folder management."""
    keyboard = [
        [InlineKeyboardButton("📰 Получить новости", callback_data='get_news')],
        [InlineKeyboardButton("➕ Добавить канал", callback_data='add_channel'), InlineKeyboardButton("➖ Удалить канал", callback_data='remove_channel')],
        [InlineKeyboardButton("📋 Список каналов", callback_data='list_channels')],
        [InlineKeyboardButton("⏰ Временной диапазон", callback_data='time_interval'), InlineKeyboardButton("📊 Количество новостей", callback_data='news_count')],
        [InlineKeyboardButton("📁 Управление папками", callback_data='manage_folders')],
        [InlineKeyboardButton("🔥Лента новостей", callback_data='news_feed')],
        [InlineKeyboardButton("⭐️ Для владельцев каналов", callback_data='for_channel_owners')],
        [InlineKeyboardButton("🗑️ Удалить все каналы", callback_data='remove_all')]
    ]
    return InlineKeyboardMarkup(keyboard)


async def create_folder_management_menu(user_id):
    """Create folder management menu with all folders."""
    # Load user data once instead of calling get_user_folders and get_active_folder_name separately
    data = await load_user_data()
    user_id_str = str(user_id)

    # Get folders and active folder from loaded data
    if user_id_str in data:
        folders = data[user_id_str].get('folders', {'Папка1': []})
        active_folder = data[user_id_str].get('active_folder', 'Папка1')
    else:
        folders = {'Папка1': []}
        active_folder = 'Папка1'

    keyboard = []

    # Add switch folder buttons
    for folder_name in folders.keys():
        active_marker = "✅ " if folder_name == active_folder else ""
        button_text = f"{active_marker}{folder_name}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f'switch_folder:{folder_name}')])

    # Add management buttons
    keyboard.append([InlineKeyboardButton("➕ Создать папку", callback_data='create_folder')])
    keyboard.append([InlineKeyboardButton("🗑️ Удалить папку", callback_data='delete_folder')])
    keyboard.append([InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')])

    return InlineKeyboardMarkup(keyboard)


def create_add_another_menu():
    """Create keyboard for adding another channel or returning to menu."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить еще канал", callback_data='add_channel')],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_remove_another_menu():
    """Create keyboard for removing another channel or returning to menu."""
    keyboard = [
        [InlineKeyboardButton("➖ Удалить еще канал", callback_data='remove_channel')],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_return_menu_button():
    """Create keyboard with only return to menu button."""
    keyboard = [
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_time_interval_menu():
    """Create keyboard for changing time interval or returning to menu."""
    keyboard = [
        [InlineKeyboardButton("⏰ Изменить диапазон", callback_data='time_interval')],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_news_count_menu():
    """Create keyboard for changing news count or returning to menu."""
    keyboard = [
        [InlineKeyboardButton("📊 Изменить количество", callback_data='news_count')],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_channel_owner_menu():
    """Create keyboard for channel owner options."""
    keyboard = [
        [InlineKeyboardButton("➕ Добавить канал в ленту", callback_data='add_to_feed')],
        [InlineKeyboardButton("➖ Удалить канал из ленты", callback_data='remove_from_feed')],
        [InlineKeyboardButton("🚫 Ограничить доступ", callback_data='restrict_access')],
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_hashtag_keyboard():
    """Create keyboard with 10 popular hashtags for channel categorization."""
    keyboard = [
        [InlineKeyboardButton("#it", callback_data='hashtag_it'),
         InlineKeyboardButton("#tech", callback_data='hashtag_tech')],
        [InlineKeyboardButton("#news", callback_data='hashtag_news'),
         InlineKeyboardButton("#business", callback_data='hashtag_business')],
        [InlineKeyboardButton("#crypto", callback_data='hashtag_crypto'),
         InlineKeyboardButton("#science", callback_data='hashtag_science')],
        [InlineKeyboardButton("#ai", callback_data='hashtag_ai'),
         InlineKeyboardButton("#startup", callback_data='hashtag_startup')],
        [InlineKeyboardButton("#fintech", callback_data='hashtag_fintech'),
         InlineKeyboardButton("#web3", callback_data='hashtag_web3')]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================================================
# Helper Functions for Code Reusability
# ============================================================================

async def validate_channel_access(channel: str, update: Update) -> tuple[bool, str]:
    """
    Validate that a Telegram channel is accessible.

    Args:
        channel: Channel name (with or without @)
        update: Telegram Update object

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    validation_msg = await update.message.reply_text(
        f"🔍 Проверяю доступность канала {channel}..."
    )

    try:
        channel_name = channel.lstrip('@')
        url = f"https://t.me/s/{channel_name}"

        client = await get_http_client()
        response = await client.get(url, timeout=10.0)
        response.raise_for_status()

        if "tgme_channel_info" not in response.text and \
           "tgme_widget_message" not in response.text:
            await validation_msg.edit_text(
                f"❌ Не удалось получить доступ к {channel}. "
                "Канал может быть приватным или не существует."
            )
            return False, "Channel not accessible"

        await validation_msg.edit_text(f"✅ Канал {channel} проверен и доступен!")
        return True, None

    except httpx.HTTPStatusError as e:
        logger.warning(f"Channel validation failed: HTTP {e.response.status_code}")
        await validation_msg.edit_text(
            f"❌ Не удалось получить доступ к {channel}. "
            "Канал может быть приватным или не существует."
        )
        return False, f"HTTP {e.response.status_code}"

    except Exception as e:
        logger.error(f"Error validating channel: {e}", exc_info=True)
        await validation_msg.edit_text(
            "😕 Произошла ошибка при проверке канала. Попробуйте позже."
        )
        return False, str(e)


async def validate_and_store_username(update: Update, context: ContextTypes.DEFAULT_TYPE, validation_msg=None) -> bool:
    """
    Validate user has Telegram username and store it in context.

    Args:
        update: Telegram Update object
        context: Bot context
        validation_msg: Optional message to edit (if channel validation already done)

    Returns:
        bool: True if username exists, False otherwise (with error message sent)
    """
    user_username = update.effective_user.username

    if user_username:
        owner_name = f"@{user_username}"
        context.user_data['form_owner_name'] = owner_name
        user_logger.info(
            f"User_{update.effective_user.id} (@{user_username}) "
            f"auto-filled owner name {owner_name}"
        )
        return True

    # User doesn't have username
    reply_markup = create_return_menu_button()
    error_msg = (
        "❌ У вас не установлен username в Telegram.\n"
        "Пожалуйста, установите username в настройках Telegram и попробуйте снова."
    )

    if validation_msg:
        await validation_msg.edit_text(error_msg, reply_markup=reply_markup)
    else:
        await update.message.reply_text(error_msg, reply_markup=reply_markup)

    context.user_data.clear()
    return False


def format_time_display(hours: int) -> str:
    """
    Format time duration in Russian with proper pluralization.

    Args:
        hours: Number of hours

    Returns:
        Formatted string like "24 часа" or "7 дней"
    """
    if hours >= 24 and hours % 24 == 0:
        days = hours // 24
        if days == 1:
            return f"{days} день"
        elif days < 5:
            return f"{days} дня"
        else:
            return f"{days} дней"
    else:
        if hours == 1:
            return f"{hours} час"
        elif hours < 5:
            return f"{hours} часа"
        else:
            return f"{hours} часов"


async def send_channel_list(update: Update, user_id: int, reply_markup=None, message_obj=None, processing_msg=None):
    """
    Send formatted channel list to user.

    Args:
        update: Telegram Update object
        user_id: User ID
        reply_markup: Optional keyboard markup to include
        message_obj: Optional message object (for query.message), defaults to update.message
        processing_msg: Optional processing message to delete after sending
    """
    data = await load_user_data()
    user_id_str = str(user_id)
    msg = message_obj or update.message

    if user_id_str not in data:
        if processing_msg:
            await processing_msg.edit_text(
                "📭 У вас нет добавленных каналов.\n"
                "Используйте кнопку '➕ Добавить канал' для добавления.",
                reply_markup=reply_markup or create_return_menu_button()
            )
        else:
            await msg.reply_text(
                "📭 У вас нет добавленных каналов.\n"
                "Используйте кнопку '➕ Добавить канал' для добавления.",
                reply_markup=reply_markup or create_return_menu_button()
            )
        return

    user_data = data[user_id_str]

    # Check if user has folders
    if 'folders' in user_data:
        folders = user_data['folders']
        active_folder = user_data.get('active_folder', 'Папка1')
        all_channels = await get_all_user_channels(user_id)

        if not all_channels:
            if processing_msg:
                await processing_msg.edit_text(
                    "📭 У вас нет добавленных каналов.\n"
                    "Используйте кнопку '➕ Добавить канал' для добавления.",
                    reply_markup=reply_markup or create_return_menu_button()
                )
            else:
                await msg.reply_text(
                    "📭 У вас нет добавленных каналов.\n"
                    "Используйте кнопку '➕ Добавить канал' для добавления.",
                    reply_markup=reply_markup or create_return_menu_button()
                )
            return

        # Build message with folders
        message_parts = [f"📋 Ваши каналы ({len(all_channels)}/{MAX_CHANNELS}):\n"]

        for folder_name, channels in folders.items():
            if channels:
                active_marker = "✅ " if folder_name == active_folder else ""
                message_parts.append(f"\n📁 {active_marker}{folder_name}:")
                for i, ch in enumerate(channels, 1):
                    message_parts.append(f"  {i}. {ch}")

        message = "\n".join(message_parts)
        if processing_msg:
            await processing_msg.edit_text(
                message,
                reply_markup=reply_markup or create_return_menu_button()
            )
        else:
            await msg.reply_text(
                message,
                reply_markup=reply_markup or create_return_menu_button()
            )
    else:
        # Fallback for old structure
        channels = user_data.get('channels', [])
        if not channels:
            if processing_msg:
                await processing_msg.edit_text(
                    "📭 У вас нет добавленных каналов.\n"
                    "Используйте кнопку '➕ Добавить канал' для добавления.",
                    reply_markup=reply_markup or create_return_menu_button()
                )
            else:
                await msg.reply_text(
                    "📭 У вас нет добавленных каналов.\n"
                    "Используйте кнопку '➕ Добавить канал' для добавления.",
                    reply_markup=reply_markup or create_return_menu_button()
                )
        else:
            channel_list = "\n".join([f"{i+1}. {ch}" for i, ch in enumerate(channels)])
            message = f"📋 Ваши каналы ({len(channels)}/{MAX_CHANNELS}):\n\n{channel_list}"
            if processing_msg:
                await processing_msg.edit_text(
                    message,
                    reply_markup=reply_markup or create_return_menu_button()
                )
            else:
                await msg.reply_text(
                    message,
                    reply_markup=reply_markup or create_return_menu_button()
                )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    logger.info(f"User {user_id} started the bot.")
    user_logger.info(f"User_{user_id} (@{username}) clicked /start")

    # Initialize user with Папка1 if new user
    data = await load_user_data()
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = {
            'folders': {
                'Папка1': []
            },
            'active_folder': 'Папка1',
            'time_limit': DEFAULT_NEWS_TIME_LIMIT_HOURS,
            'max_summary_posts': DEFAULT_MAX_SUMMARY_POSTS,
            'news_requests': {}
        }
        await save_user_data(data)
        logger.info(f"Created Папка1 for new user {user_id}")

    welcome_message = (
        "⭐️Привет! Я ваш личный доставщик новостей!\n"
        "• Не хватает времени прочитать все telegram каналы?\n"
        "• Устали читать одну и туже новость в разных каналах?\n"
        "• Информационный шум вызывает тревожность?\n\n"
         "💻Как это работает?\n"
        "• Я читаю все ваши каналы и объединяю их новости\n"
        "• Больше никаких дубликатов!\n"
        "• Читаете меньше, а знаете больше\n"
        "• Получаете только уникальную и важную информацию\n\n"
        "📖 Каналы по одной теме = залог хороших новостей!"
    )

    inline_markup = create_main_menu()
    persistent_markup = create_persistent_keyboard()
    await update.message.reply_text(welcome_message, reply_markup=persistent_markup)
    await update.message.reply_text("Выберите действие:", reply_markup=inline_markup)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked /help")

    help_text = (
        "🤖 Доступные команды:\n\n"
        "/start - Показать главное меню с кнопками\n"
        "/help - Показать это сообщение помощи\n\n"
        "📋 Главное меню включает:\n"
        "• ➕ Добавить канал\n"
        "• ➖ Удалить канал\n"
        "• 📋 Список каналов\n"
        "• ⏰ Временной диапазон\n"
        "• 📊 Количество новостей\n"
        "• 📰 Получить новости\n"
        "• ⭐️ Для владельцев каналов\n"
        "• 🗑️ Удалить все каналы\n\n"
        "💡 Совет: Используйте /start для доступа к меню с кнопками!"
    )
    await update.message.reply_text(help_text)


async def restore_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /restore_backup admin command."""
    user = update.effective_user
    admin_id = ADMIN_CHAT_ID_INT

    if admin_id is None:
        await update.message.reply_text('ADMIN_CHAT_ID is not configured. Set it in the environment to enable restores.')
        return

    if user.id != admin_id:
        await update.message.reply_text('You are not authorized to use this command.')
        return

    backups = list_user_data_backups()

    if not backups:
        await update.message.reply_text('No backups are currently available.')
        return

    if not context.args:
        lines = ['Available backups:']
        for idx, backup in enumerate(backups, 1):
            timestamp = datetime.utcfromtimestamp(backup['mtime']).strftime('%Y-%m-%d %H:%M:%S')
            lines.append(f"{idx}. {backup['name']} (UTC {timestamp})")
        lines.append('')
        lines.append('Run `/restore_backup <number>` or `/restore_backup latest` to restore.')
        await update.message.reply_text("\n".join(lines))
        return

    choice = context.args[0].strip().lower()
    if choice == 'latest':
        selection_index = 0
    else:
        try:
            selection_index = int(choice) - 1
        except ValueError:
            await update.message.reply_text('Invalid selection. Use `/restore_backup` to see available backups.')
            return

    if selection_index < 0 or selection_index >= len(backups):
        await update.message.reply_text('Selection out of range. Use `/restore_backup` to view options.')
        return

    selected = backups[selection_index]
    try:
        await restore_user_data_from_backup(selected['path'])
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.error('Failed restoring backup %s: %s', selected['path'], exc)
        await update.message.reply_text(f'Failed to restore backup: {exc}')
        return
    except Exception as exc:
        logger.exception('Unexpected error while restoring backup %s', selected['path'])
        await update.message.reply_text('Unexpected error occurred during restore.')
        return

    user_logger.info(f"Admin_{user.id} restored backup {selected['name']}")
    logger.info('Admin %s restored backup %s', user.id, selected['path'])
    timestamp = datetime.utcfromtimestamp(selected['mtime']).strftime('%Y-%m-%d %H:%M:%S')
    await update.message.reply_text(
        f"Backup {selected['name']} (UTC {timestamp}) restored successfully."
    )


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if channel name is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /add (no channel specified)")
        await update.message.reply_text("❌ Укажите название канала. Например: /add @channelname")
        return

    channel = context.args[0]

    # Validate channel format (should start with @)
    if not channel.startswith('@'):
        await update.message.reply_text("❌ Название канала должно начинаться с @")
        return

    # Get current user channels (from active folder)
    channels = await get_user_channels(user_id)
    # Get all channels across all folders
    all_channels = await get_all_user_channels(user_id)

    # Check if channel already exists in ANY folder (no duplicates allowed)
    if channel in all_channels:
        await update.message.reply_text(f"ℹ️ {channel} уже добавлен в одну из Ваших папок.")
        return

    # Check channel limit (global across all folders)
    if len(all_channels) >= MAX_CHANNELS:
        await update.message.reply_text(f"❌ Вы достигли максимального лимита в {MAX_CHANNELS} каналов.")
        return

    # Validate channel accessibility
    is_valid, error_msg = await validate_channel_access(channel, update)

    if not is_valid:
        logger.warning(f"User {user_id} tried to add inaccessible channel {channel}: {error_msg}")
        return

    # Add channel
    channels.append(channel)
    await set_user_channels(user_id, channels)

    logger.info(f"User {user_id} added channel {channel}.")
    user_logger.info(f"User_{user_id} (@{username}) specified /add {channel}")
    await update.message.reply_text(f"✅ {channel} был добавлен.")


async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if channel name is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /remove (no channel specified)")
        await update.message.reply_text("❌ Укажите название канала. Например: /remove @channelname")
        return

    channel = context.args[0]

    # Get current user channels
    channels = await get_user_channels(user_id)

    # Check if channel exists in user's list
    if channel not in channels:
        await update.message.reply_text(f"❌ {channel} не найден в вашем списке.")
        return

    # Remove channel
    channels.remove(channel)
    await set_user_channels(user_id, channels)

    user_logger.info(f"User_{user_id} (@{username}) specified /remove {channel}")
    await update.message.reply_text(f"🗑️ {channel} был удален.")


async def remove_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove_all command."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked /remove_all")

    # Get current user channels
    channels = await get_user_channels(user_id)

    if not channels:
        await update.message.reply_text("📭 У вас нет добавленных каналов.")
        return

    # Remove all channels
    channel_count = len(channels)
    await set_user_channels(user_id, [])

    await update.message.reply_text(f"🗑️ Все каналы ({channel_count}) были удалены.")


async def list_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command - show all folders and channels."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked /list")

    await send_channel_list(update, user_id)


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /time command - set news time range."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if hours value is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /time (view current)")
        current_time = await get_user_time_limit(user_id)

        # Format display: hours or days
        display = format_time_display(current_time)

        await update.message.reply_text(
            f"⏰ Текущий временной диапазон: {display}\n\n"
            f"Чтобы изменить, используйте:\n"
            f"• /time <часы> (например: /time 24)\n"
            f"• /time <дни>d (например: /time 7d)\n"
            f"Максимум: {MAX_NEWS_TIME_LIMIT_HOURS} часов (30 дней)"
        )
        return

    try:
        input_value = context.args[0].lower()

        # Check if input is in days format (e.g., "7d")
        if input_value.endswith('d'):
            days = int(input_value[:-1])
            hours = days * 24
            input_type = "days"
        else:
            hours = int(input_value)
            input_type = "hours"

        input_display = format_time_display(hours)

        # Validate hours
        if hours < 1:
            await update.message.reply_text("❌ Временной диапазон должен быть больше 0.")
            return

        if hours > MAX_NEWS_TIME_LIMIT_HOURS:
            await update.message.reply_text(
                f"❌ Временной диапазон не может превышать {MAX_NEWS_TIME_LIMIT_HOURS} часов (30 дней)."
            )
            return

        # Set the new time limit
        await set_user_time_limit(user_id, hours)
        logger.info(f"User {user_id} set time limit to {hours} hours ({input_type}: {input_display}).")
        user_logger.info(f"User_{user_id} (@{username}) specified /time {context.args[0]}")

        # Format success message
        if hours >= 24 and hours % 24 == 0:
            equivalent = f"{input_display} ({hours} часов)"
        else:
            equivalent = input_display

        await update.message.reply_text(
            f"✅ Временной диапазон установлен: {equivalent}\n"
            f"Команда /news будет собирать новости за последние {equivalent.split('(')[0].strip()}."
        )

    except ValueError:
        await update.message.reply_text(
            "❌ Укажите корректное значение.\n"
            "Примеры: /time 24 или /time 7d"
        )


async def posts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /posts command - set maximum number of news summaries."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if posts value is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /posts (view current)")
        current_max = await get_user_max_posts(user_id)
        await update.message.reply_text(
            f"📊 Текущее количество новостей: {current_max}\n\n"
            f"Чтобы изменить, используйте: /posts <количество>\n"
            f"Например: /posts 10\n"
            f"Максимум: {MAX_SUMMARY_POSTS_LIMIT} новостей"
        )
        return

    try:
        max_posts = int(context.args[0])

        # Validate max_posts
        if max_posts < 1:
            await update.message.reply_text("❌ Количество новостей должно быть больше 0.")
            return

        if max_posts > MAX_SUMMARY_POSTS_LIMIT:
            await update.message.reply_text(
                f"❌ Количество новостей не может превышать {MAX_SUMMARY_POSTS_LIMIT}."
            )
            return

        # Set the new max posts
        await set_user_max_posts(user_id, max_posts)
        logger.info(f"User {user_id} set max posts to {max_posts}.")
        user_logger.info(f"User_{user_id} (@{username}) specified /posts {max_posts}")

        await update.message.reply_text(
            f"✅ Количество новостей установлено: {max_posts}\n"
            f"Команда /news будет показывать до {max_posts} новостей."
        )

    except ValueError:
        await update.message.reply_text("❌ Укажите корректное число. Например: /posts 10")


def parse_subscriber_count(text: str) -> int:
    """
    Parse subscriber count text to integer.

    Args:
        text: Subscriber count string (e.g., "1.2M subscribers", "53K members", "987 subscribers")

    Returns:
        Integer count, or 0 if parsing fails
    """
    if not text:
        return 0

    try:
        # Extract numeric part and suffix
        text = text.strip().lower()

        # Remove common words like "subscribers", "members", etc.
        for word in ['subscribers', 'members', 'subscriber', 'member']:
            text = text.replace(word, '')

        # Remove extra spaces
        text = text.strip()

        # Handle millions (M)
        if 'm' in text:
            num_str = text.replace('m', '').strip()
            num = float(num_str)
            return int(num * 1_000_000)

        # Handle thousands (K)
        elif 'k' in text:
            num_str = text.replace('k', '').strip()
            num = float(num_str)
            return int(num * 1_000)

        # Handle plain numbers
        else:
            # Remove any remaining commas or spaces
            num_str = text.replace(',', '').replace(' ', '')
            return int(float(num_str))

    except Exception as e:
        logger.warning(f"Failed to parse subscriber count '{text}': {e}")
        return 0


async def scrape_channel(channel_name: str, time_limit_hours: int = DEFAULT_NEWS_TIME_LIMIT_HOURS) -> list:
    """
    Scrape recent posts from a public Telegram channel.

    Args:
        channel_name: Channel name (e.g., '@channelname')

    Returns:
        List of dictionaries with post data including:
        - text: Full text content of the post
        - channel: Channel name with @ prefix
        - url: Direct URL to the post (e.g., https://t.me/channel/123)
        - timestamp: Publication time as datetime object (timezone-aware)
        - subscriber_count: Total subscriber count for the channel
    """
    # Remove @ if present
    channel = channel_name.lstrip('@')
    url = f"https://t.me/s/{channel}"

    posts = []

    # Calculate time cutoff (timezone-aware)
    time_cutoff = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)

    try:
        http_client = await get_http_client()
        response = await http_client.get(url, timeout=30.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract channel subscriber count
        subscriber_count = 0
        subscriber_elem = soup.find('div', class_='tgme_channel_info_counter')
        if subscriber_elem:
            subscriber_text = subscriber_elem.get_text(strip=True)
            subscriber_count = parse_subscriber_count(subscriber_text)
            logger.debug(f"Channel {channel_name} has {subscriber_count} subscribers")

        # Find all post messages
        message_widgets = soup.find_all('div', class_='tgme_widget_message')

        post_count = 0
        for message_widget in message_widgets:
            if post_count >= MAX_POSTS_PER_CHANNEL:
                break

            # Extract post text
            post_elem = message_widget.find('div', class_='tgme_widget_message_text')
            if not post_elem:
                continue

            text = post_elem.get_text(strip=True)

            # Remove all URLs from text (except t.me links which are post references)
            import re
            text = re.sub(r'https?://(?!t\.me/)[^\s]+', '', text)
            text = re.sub(r'www\.[^\s]+', '', text)
            text = ' '.join(text.split())  # Clean up extra whitespace

            # Skip empty or very short posts
            if len(text) < 50:
                continue

            # Extract unique post URL from data-post attribute
            post_url = None
            data_post = message_widget.get('data-post')
            if data_post:
                # data-post format is typically "channel_username/post_id"
                post_url = f"https://t.me/{data_post}"

            # Extract timestamp
            post_timestamp = None
            time_elem = message_widget.find('time')
            if time_elem and time_elem.get('datetime'):
                try:
                    # Parse ISO format timestamp (e.g., "2025-10-07T10:30:00+00:00")
                    post_time_str = time_elem['datetime']
                    post_time = datetime.fromisoformat(post_time_str.replace('Z', '+00:00'))

                    if post_time.tzinfo is None:
                        logger.debug(f"Assuming UTC for naive timestamp in {channel_name}: {post_time_str}")
                        post_time = post_time.replace(tzinfo=timezone.utc)

                    # Store the datetime object for future use (timezone-aware)
                    post_timestamp = post_time

                    # Skip posts older than time limit (compare timezone-aware datetimes)
                    if post_timestamp < time_cutoff:
                        logger.debug(f"Skipping old post from {channel_name}: {post_timestamp} (cutoff: {time_cutoff})")
                        continue
                except Exception as e:
                    logger.warning(f"Could not parse timestamp for post in {channel_name}: {e}")
                    # Skip posts with unparseable timestamps to enforce time filter
                    continue

            if not post_timestamp:
                logger.debug(f"Skipping post without timestamp from {channel_name}")
                continue

            posts.append({
                'text': text,
                'channel': channel_name,
                'url': post_url,
                'timestamp': post_timestamp,
                'subscriber_count': subscriber_count
            })
            post_count += 1

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            logger.warning(f"Channel {channel_name} not found (404)")
        else:
            logger.warning(f"HTTP error scraping {channel_name}: {e.response.status_code}")
    except httpx.TimeoutException:
        logger.error(f"Timeout while scraping {channel_name}")
    except Exception as e:
        logger.error(f"Error scraping {channel_name}: {str(e)}", exc_info=True)

    return posts


async def get_embeddings(texts: list) -> list:
    """
    Get embeddings for a list of texts using Google's text-embedding model.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (numpy arrays)
    """
    if not texts:
        return []

    try:
        embeddings = []

        # Process in batches to avoid API limits
        batch_size = 100  # Google API allows up to 100 per batch

        # Run embedding calls in thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]

            # Use Google's embedding model in executor to prevent blocking
            # Note: text-embedding-004 is the correct model name for Google's API
            result = await loop.run_in_executor(
                None,
                lambda b=batch: genai.embed_content(
                    model="models/text-embedding-004",
                    content=b,
                    task_type="retrieval_document"
                )
            )

            # Extract embeddings from result
            for embedding in result['embedding']:
                embeddings.append(np.array(embedding))

        return embeddings

    except Exception as e:
        logger.error(f"Error getting embeddings: {str(e)}", exc_info=True)
        return []


async def cluster_posts(posts: list) -> list:
    """
    Cluster similar posts using DBSCAN and embeddings.

    Args:
        posts: List of post dictionaries with 'text' field

    Returns:
        List of clusters, where each cluster is a list of post dictionaries
    """
    if not posts:
        return []

    # Get embeddings for all posts
    texts = [post['text'] for post in posts]
    embeddings = await get_embeddings(texts)

    if not embeddings or len(embeddings) != len(posts):
        logger.warning("Failed to get embeddings")
        return [[post] for post in posts]  # Return each post as its own cluster

    # Create embedding matrix directly (avoid storing in posts to save memory)
    embedding_matrix = np.array(embeddings)

    # Configure and run DBSCAN
    # eps = 1 - SIMILARITY_THRESHOLD (cosine distance from cosine similarity)
    eps = 1 - SIMILARITY_THRESHOLD
    min_samples = 2  # Minimum posts to form a cluster

    # Initialize and fit DBSCAN
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='cosine')
    cluster_labels = db.fit_predict(embedding_matrix)

    # Group posts by cluster label using defaultdict for efficiency
    cluster_dict = defaultdict(list)
    for post, label in zip(posts, cluster_labels):
        cluster_dict[label].append(post)

    # Build cluster list
    clusters = []

    # Add valid clusters (labels >= 0)
    for label in sorted(cluster_dict.keys()):
        if label >= 0:
            clusters.append(cluster_dict[label])

    # Add noise posts (label = -1) as single-item clusters
    if -1 in cluster_dict:
        clusters.extend([noise_post] for noise_post in cluster_dict[-1])

    logger.info(f"DBSCAN clustering: {len(posts)} posts -> {len(clusters)} clusters (noise: {len(cluster_dict.get(-1, []))})")

    return clusters


def get_gemini_model():
    """Get or create cached Gemini model instance."""
    global _gemini_model
    if _gemini_model is None:
        _gemini_model = genai.GenerativeModel('gemini-flash-lite-latest')
    return _gemini_model


async def summarize_cluster(posts: list, retry_count: int = 3) -> dict:
    """
    Summarize a cluster of similar posts using Gemini.

    Args:
        posts: List of post dictionaries from the same story
        retry_count: Number of retries for API calls (default: 3)

    Returns:
        Dictionary with 'headline' and 'summary' fields
    """
    if not posts:
        return {'headline': '', 'summary': '', 'channels': []}

    # Select the longest post as the most representative
    representative_post = max(posts, key=lambda p: len(p['text']))

    # Collect all channels that covered this story (using set for deduplication)
    channels = list({post['channel'] for post in posts})

    # Collect post URLs with their channels for creating links
    post_links = [{'channel': post['channel'], 'url': post['url']}
                  for post in posts if post.get('url')]

    prompt = f"""Вы - краткий новостной аналитик. Ваша задача - обобщить новостной сюжет на основе следующего текста.

Предоставьте:
1. Один впечатляющий заголовок (максимум 15 слов)
2. Краткое резюме ключевых фактов из 2-3 пунктов

ВАЖНО: НЕ ВКЛЮЧАЙТЕ никаких ссылок или гиперссылок в заголовок и резюме. Используйте только обычный текст. Если в посте есть ссылка сделай ее простым текстом! Не превращайте слова, которые выглядят как домены (например: "x.ai", "X.AI", "OpenAI.com", Epoch.AI" и другие) в ссылки.

Текст новости:
{representative_post['text']}

Формат ответа:
ЗАГОЛОВОК: [ваш заголовок]

РЕЗЮМЕ:
• [первый ключевой факт]
• [второй ключевой факт]
• [третий ключевой факт, если необходимо]"""

    # Configure generation parameters (reused across retries)
    generation_config = genai.types.GenerationConfig(
        temperature=0.3,
        max_output_tokens=500,
    )

    # Configure safety settings to be less restrictive (reused across retries)
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    # Get cached model instance
    model = get_gemini_model()

    # Retry loop with exponential backoff
    for attempt in range(retry_count):
        try:
            # Use semaphore to limit concurrent API calls
            async with _gemini_semaphore:
                # Generate content (run in thread pool since genai is synchronous)
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: model.generate_content(
                        prompt,
                        generation_config=generation_config,
                        safety_settings=safety_settings
                    )
                )

            # Check if response was blocked
            if not response.candidates:
                raise ValueError("Response was blocked by safety filters")

            if response.candidates[0].finish_reason not in [1, 0]:  # 0=UNSPECIFIED, 1=STOP (normal)
                raise ValueError(f"Response blocked with finish_reason: {response.candidates[0].finish_reason}")

            content = response.text

            # Check if content is None or empty
            if not content:
                raise ValueError("API returned empty response")

            # Parse the response
            lines = content.strip().split('\n')
            headline = ''
            summary_points = []

            in_summary = False
            for line in lines:
                line = line.strip()
                if line.startswith('ЗАГОЛОВОК:'):
                    headline = line.replace('ЗАГОЛОВОК:', '').strip()
                    # Remove ** markdown formatting from headline
                    headline = headline.strip('*').strip()
                elif line.startswith('РЕЗЮМЕ:'):
                    in_summary = True
                elif in_summary and line:  # Capture all non-empty lines after РЕЗЮМЕ
                    summary_points.append(line)

            summary = '\n'.join(summary_points)

            return {
                'headline': headline,
                'summary': summary,
                'channels': channels,
                'post_links': post_links,
                'count': len(posts)
            }

        except Exception as e:
            is_last_attempt = (attempt == retry_count - 1)
            logger.warning(f"Error summarizing cluster (attempt {attempt + 1}/{retry_count}): {str(e)}")

            if is_last_attempt:
                # All retries failed, log error and return fallback
                logger.error(f"Failed to summarize cluster after {retry_count} attempts: {str(e)}", exc_info=True)
                return {
                    'headline': 'Ошибка обработки',
                    'summary': representative_post['text'][:300] + '...',
                    'channels': channels,
                    'post_links': post_links,
                    'count': len(posts)
                }

            # Calculate wait time with exponential backoff
            wait_time = (2 ** attempt)  # Default: 1s, 2s, 4s

            # Try to extract retry_delay from ResourceExhausted exception
            if 'retry_delay' in str(e):
                try:
                    match = re.search(r'retry_delay\s*{\s*seconds:\s*(\d+)', str(e))
                    if match:
                        suggested_delay = int(match.group(1))
                        # Use suggested delay but cap at 30 seconds to avoid excessive waiting
                        wait_time = min(suggested_delay, 30)
                        logger.info(f"API suggested retry delay: {suggested_delay}s, using {wait_time}s")
                except Exception:
                    pass  # Fall back to exponential backoff if parsing fails

            logger.info(f"Retrying in {wait_time} seconds...")
            await asyncio.sleep(wait_time)


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    if query.data == 'return_to_menu':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Return to menu' button")
        welcome_message = (
            "Вам необходимо добавить каналы. После добавления каналов, "
            "вы сможете получать новости.\n\n"
            "Выберите действие из меню:"
        )
        reply_markup = create_main_menu()
        await query.message.reply_text(welcome_message, reply_markup=reply_markup)
        return ConversationHandler.END

    elif query.data == 'add_channel':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Add channel' button")
        await query.message.reply_text(
            "➕ Добавить канал\n\n"
            "Введите 1 канал в строку ввода.\n"
            "Пример: @channel01"
        )
        return WAITING_FOR_CHANNEL_ADD

    elif query.data == 'remove_channel':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Remove channel' button")
        await query.message.reply_text(
            "➖ Удалить канал\n\n"
            "Введите 1 канал в строку ввода.\n"
            "Пример: @channel01"
        )
        return WAITING_FOR_CHANNEL_REMOVE

    elif query.data == 'list_channels':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Channel List' button")
        # Send immediate feedback
        processing_msg = await query.message.reply_text("⏳ Загружаю список каналов...")

        reply_markup = create_return_menu_button()

        await send_channel_list(update, user_id, reply_markup=reply_markup, message_obj=query.message, processing_msg=processing_msg)

        return ConversationHandler.END

    elif query.data == 'time_interval':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Time Interval' button")
        current_time = await get_user_time_limit(user_id)

        # Format display: hours or days
        display = format_time_display(current_time)

        await query.message.reply_text(
            f"⏰ Текущий временной диапазон: {display}\n\n"
            f"Чтобы изменить диапазон, введите:\n"
            f"• Количество часов (например: 24)\n"
            f"• Количество дней с буквой 'd' (например: 7d)\n"
            f"Максимум: {MAX_NEWS_TIME_LIMIT_HOURS} часов (30 дней)"
        )
        return WAITING_FOR_TIME_INTERVAL

    elif query.data == 'news_count':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Number of News' button")
        current_max = await get_user_max_posts(user_id)
        await query.message.reply_text(
            f"📊 Текущее количество новостей: {current_max}\n\n"
            f"Чтобы изменить, введите количество (например: 10)\n"
            f"Максимум: {MAX_SUMMARY_POSTS_LIMIT} новостей"
        )
        return WAITING_FOR_NEWS_COUNT

    elif query.data == 'get_news':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Get News' button")
        # Send immediate feedback before processing
        processing_msg = await query.message.reply_text(
            "⏳ Начинаю сбор новостей...\n"
            "Это займёт несколько секунд."
        )
        # Call the news command function
        await news_command_internal(update, context, processing_msg)
        return ConversationHandler.END

    elif query.data == 'news_feed':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'News Feed' button")
        reply_markup = create_return_menu_button()
        message_text = "Здесь будут каналы по темам “скоро” ... "
        await query.message.reply_text(message_text, reply_markup=reply_markup)
        return ConversationHandler.END

    elif query.data == 'for_channel_owners':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'For channel owners' button")
        reply_markup = create_channel_owner_menu()
        message_text = (
            "⭐️ Для владельцев каналов\n\n"
            "Для владельцев каналов мы предлагаем возможность добавить каналы в ленту новостей.\n\n"
            "Выберите действие:"
        )
        await query.message.reply_text(message_text, reply_markup=reply_markup)
        return ConversationHandler.END

    elif query.data == 'add_to_feed':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Add to feed' button")
        await query.message.reply_text(
            "➕ Добавить канал в ленту\n\n"
            "Введите название канала:\n"
            "Пример: @channels01"
        )
        return WAITING_FOR_ADD_TO_FEED_CHANNEL

    elif query.data == 'remove_from_feed':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Remove from feed' button")
        await query.message.reply_text(
            "➖ Удалить канал из ленты\n\n"
            "Введите название канала:\n"
            "Пример: @channels01"
        )
        return WAITING_FOR_REMOVE_FROM_FEED_CHANNEL

    elif query.data == 'restrict_access':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Restrict access' button")
        await query.message.reply_text(
            "🚫 Ограничить доступ\n\n"
            "Введите название канала:\n"
            "Пример: @channels01"
        )
        return WAITING_FOR_RESTRICT_ACCESS_CHANNEL

    elif query.data.startswith('hashtag_'):
        # Handle hashtag selection
        hashtag = '#' + query.data.replace('hashtag_', '')
        context.user_data['form_hashtag'] = hashtag
        user_logger.info(f"User_{user_id} (@{username}) selected hashtag {hashtag}")
        await query.message.reply_text(
            f"✅ Выбран хештег: {hashtag}\n\n"
            f"Напишите краткое описание вашего канала (максимум 30 символов):"
        )
        return WAITING_FOR_ADD_TO_FEED_DESCRIPTION

    elif query.data == 'remove_all':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Delete All Channels' button")
        # Send immediate feedback
        processing_msg = await query.message.reply_text("⏳ Удаляю все каналы...")

        channels = await get_user_channels(user_id)
        reply_markup = create_return_menu_button()

        if not channels:
            await processing_msg.edit_text(
                "📭 У вас нет добавленных каналов.",
                reply_markup=reply_markup
            )
        else:
            channel_count = len(channels)
            await set_user_channels(user_id, [])
            await processing_msg.edit_text(
                f"🗑️ Все каналы ({channel_count}) были удалены.",
                reply_markup=reply_markup
            )
        return ConversationHandler.END

    elif query.data == 'manage_folders':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Manage Folders' button")
        # Send immediate feedback
        processing_msg = await query.message.reply_text("⏳ Загружаю папки...")

        active_folder = await get_active_folder_name(user_id)
        folders = await get_user_folders(user_id)
        folder_count = len(folders)

        reply_markup = await create_folder_management_menu(user_id)
        await processing_msg.edit_text(
            f"📁 Управление папками\n\n"
            f"✅ Активная папка: {active_folder}\n"
            f"📊 Всего папок: {folder_count}\n\n"
            f"Выберите папку для переключения или создайте новую:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data.startswith('switch_folder:'):
        folder_name = query.data.replace('switch_folder:', '')
        user_logger.info(f"User_{user_id} (@{username}) switching to folder '{folder_name}'")

        # Send immediate feedback
        processing_msg = await query.message.reply_text(f"⏳ Переключаюсь на папку {folder_name}...")

        if await switch_active_folder(user_id, folder_name):
            reply_markup = await create_folder_management_menu(user_id)
            await processing_msg.edit_text(
                f"✅ Переключено на папку: {folder_name}\n\n"
                f"Теперь все операции с каналами будут применяться к этой папке.\n"
                f"Команда /news будет показывать новости из каналов этой папки.",
                reply_markup=reply_markup
            )
        else:
            await processing_msg.edit_text("❌ Не удалось переключить папку.")
        return ConversationHandler.END

    elif query.data == 'create_folder':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Create Folder' button")
        await query.message.reply_text(
            "➕ Создание новой папки\n\n"
            "Введите название новой папки (максимум 10 символов):"
        )
        return WAITING_FOR_NEW_FOLDER_NAME

    elif query.data == 'delete_folder':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Delete Folder' button")
        folders = await get_user_folders(user_id)

        if len(folders) == 1:
            reply_markup = await create_folder_management_menu(user_id)
            await query.message.reply_text(
                "❌ Нельзя удалить единственную папку.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Create buttons for each folder
        keyboard = []
        for folder_name in folders.keys():
            keyboard.append([InlineKeyboardButton(f"🗑️ {folder_name}", callback_data=f'confirm_delete_folder:{folder_name}')])
        keyboard.append([InlineKeyboardButton("🏠 Вернуться в меню", callback_data='manage_folders')])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text(
            "🗑️ Удаление папки\n\n"
            "Выберите папку для удаления.\n"
            "⚠️ Все каналы в папке будут удалены:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data.startswith('confirm_delete_folder:'):
        folder_name = query.data.replace('confirm_delete_folder:', '')
        user_logger.info(f"User_{user_id} (@{username}) confirming delete folder '{folder_name}'")

        # Send immediate feedback
        processing_msg = await query.message.reply_text(f"⏳ Удаляю папку {folder_name}...")

        if await delete_folder(user_id, folder_name):
            reply_markup = await create_folder_management_menu(user_id)
            await processing_msg.edit_text(
                f"✅ Папка '{folder_name}' удалена.",
                reply_markup=reply_markup
            )
        else:
            reply_markup = await create_folder_management_menu(user_id)
            await processing_msg.edit_text(
                f"❌ Не удалось удалить папку '{folder_name}'.",
                reply_markup=reply_markup
            )
        return ConversationHandler.END

    return ConversationHandler.END


async def handle_add_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for adding a channel."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Validate channel format (should start with @)
    if not channel.startswith('@'):
        await update.message.reply_text("❌ Название канала должно начинаться с @")
        return WAITING_FOR_CHANNEL_ADD

    # Get current user channels (from active folder)
    channels = await get_user_channels(user_id)
    # Get all channels across all folders
    all_channels = await get_all_user_channels(user_id)

    # Check if channel already exists in ANY folder (no duplicates allowed)
    if channel in all_channels:
        reply_markup = create_add_another_menu()
        await update.message.reply_text(
            f"ℹ️ {channel} уже добавлен в одну из Ваших папок.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Check channel limit (global across all folders)
    if len(all_channels) >= MAX_CHANNELS:
        reply_markup = create_main_menu()
        await update.message.reply_text(
            f"❌ Вы достигли максимального лимита в {MAX_CHANNELS} каналов.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Validate channel accessibility
    is_valid, error_msg = await validate_channel_access(channel, update)

    reply_markup = create_add_another_menu()

    if not is_valid:
        logger.warning(f"User {user_id} tried to add inaccessible channel {channel}: {error_msg}")
        await update.message.reply_text(
            "Выберите действие:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Add channel
    channels.append(channel)
    await set_user_channels(user_id, channels)

    logger.info(f"User {user_id} added channel {channel}.")
    user_logger.info(f"User_{user_id} (@{username}) added channel {channel} via button")

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def handle_remove_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for removing a channel."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Get current user channels
    channels = await get_user_channels(user_id)

    # Check if channel exists in user's list
    if channel not in channels:
        reply_markup = create_remove_another_menu()
        await update.message.reply_text(
            f"❌ {channel} не найден в вашем списке.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Remove channel
    channels.remove(channel)
    await set_user_channels(user_id, channels)

    user_logger.info(f"User_{user_id} (@{username}) removed channel {channel} via button")
    reply_markup = create_remove_another_menu()
    await update.message.reply_text(
        f"🗑️ {channel} был удален.",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def handle_time_interval_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for setting time interval."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    input_value = update.message.text.strip().lower()

    try:
        # Check if input is in days format (e.g., "7d")
        if input_value.endswith('d'):
            days = int(input_value[:-1])
            hours = days * 24
            input_type = "days"
        else:
            hours = int(input_value)
            input_type = "hours"

        input_display = format_time_display(hours)

        # Validate hours
        if hours < 1:
            reply_markup = create_time_interval_menu()
            await update.message.reply_text(
                "❌ Временной диапазон должен быть больше 0.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        if hours > MAX_NEWS_TIME_LIMIT_HOURS:
            reply_markup = create_time_interval_menu()
            await update.message.reply_text(
                f"❌ Временной диапазон не может превышать {MAX_NEWS_TIME_LIMIT_HOURS} часов (30 дней).",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Set the new time limit
        await set_user_time_limit(user_id, hours)
        logger.info(f"User {user_id} set time limit to {hours} hours ({input_type}: {input_display}).")
        user_logger.info(f"User_{user_id} (@{username}) set time to {input_value} via button")

        # Format success message
        if hours >= 24 and hours % 24 == 0:
            equivalent = f"{input_display} ({hours} часов)"
        else:
            equivalent = input_display

        reply_markup = create_time_interval_menu()
        await update.message.reply_text(
            f"✅ Временной диапазон установлен: {equivalent}\n"
            f"Команда 'Получить новости' будет собирать новости за последние {equivalent.split('(')[0].strip()}.",
            reply_markup=reply_markup
        )

    except ValueError:
        reply_markup = create_time_interval_menu()
        await update.message.reply_text(
            "❌ Укажите корректное значение.\n"
            "Примеры: 24 или 7d",
            reply_markup=reply_markup
        )

    return ConversationHandler.END


async def handle_news_count_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for setting news count."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    try:
        max_posts = int(update.message.text.strip())

        # Validate max_posts
        if max_posts < 1:
            reply_markup = create_news_count_menu()
            await update.message.reply_text(
                "❌ Количество новостей должно быть больше 0.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        if max_posts > MAX_SUMMARY_POSTS_LIMIT:
            reply_markup = create_news_count_menu()
            await update.message.reply_text(
                f"❌ Количество новостей не может превышать {MAX_SUMMARY_POSTS_LIMIT}.",
                reply_markup=reply_markup
            )
            return ConversationHandler.END

        # Set the new max posts
        await set_user_max_posts(user_id, max_posts)
        logger.info(f"User {user_id} set max posts to {max_posts}.")
        user_logger.info(f"User_{user_id} (@{username}) set posts to {max_posts} via button")

        reply_markup = create_news_count_menu()
        await update.message.reply_text(
            f"✅ Количество новостей установлено: {max_posts}\n"
            f"Команда 'Получить новости' будет показывать до {max_posts} новостей.",
            reply_markup=reply_markup
        )

    except ValueError:
        reply_markup = create_news_count_menu()
        await update.message.reply_text(
            "❌ Укажите корректное число. Например: 10",
            reply_markup=reply_markup
        )

    return ConversationHandler.END


async def handle_new_folder_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for creating a new folder."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    folder_name = update.message.text.strip()

    # Validate folder name
    if len(folder_name) == 0:
        await update.message.reply_text("❌ Название папки не может быть пустым.")
        return WAITING_FOR_NEW_FOLDER_NAME

    if len(folder_name) > 10:
        await update.message.reply_text("❌ Название папки не может превышать 10 символов.")
        return WAITING_FOR_NEW_FOLDER_NAME

    # Create the folder
    if await create_folder(user_id, folder_name):
        logger.info(f"User {user_id} created folder '{folder_name}'.")
        user_logger.info(f"User_{user_id} (@{username}) created folder '{folder_name}'")

        reply_markup = await create_folder_management_menu(user_id)
        await update.message.reply_text(
            f"✅ Папка '{folder_name}' создана!\n\n"
            f"Вы можете переключиться на неё и добавлять каналы.",
            reply_markup=reply_markup
        )
    else:
        reply_markup = await create_folder_management_menu(user_id)
        await update.message.reply_text(
            f"❌ Папка '{folder_name}' уже существует.",
            reply_markup=reply_markup
        )

    return ConversationHandler.END


async def handle_return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the persistent 'Return to menu' button press."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked persistent 'Return to menu' button")

    welcome_message = (
        "🏠 Главное меню\n\n"
        "Выберите действие из меню ниже:"
    )

    reply_markup = create_main_menu()
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def news_command_internal(update: Update, context: ContextTypes.DEFAULT_TYPE, processing_msg=None):
    """Internal news command handler that works with both command and button."""
    # Get the query object if it's from a button callback
    query = update.callback_query if update.callback_query else None

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    logger.info(f"User {user_id} ran /news command.")
    user_logger.info(f"User_{user_id} (@{username}) clicked /news")

    # Load user data once to avoid multiple redundant loads
    data = await load_user_data()
    user_id_str = str(user_id)
    user_data = data.get(user_id_str, {})

    # Check rate limit (inline to avoid extra load)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    last_news_date = user_data.get('last_news_date', '')
    news_request_count = user_data.get('news_request_count', 0)

    if last_news_date != today:
        news_request_count = 0

    remaining = MAX_NEWS_REQUESTS_PER_DAY - news_request_count
    is_allowed = news_request_count < MAX_NEWS_REQUESTS_PER_DAY

    if not is_allowed:
        message_text = (
            f"❌ Вы достигли дневного лимита запросов новостей\n"
            f"({MAX_NEWS_REQUESTS_PER_DAY} запросов в день)\n"
            f"Мы используем время UTC для всех наших пользователей\n"
            f"В 00:00:01 UTC количество запросов обновиться\n"
            f"Можно будет снова получать новости"
        )
        if processing_msg:
            await processing_msg.edit_text(message_text)
        elif query:
            await query.message.reply_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return

    # Get user's channels and preferences from loaded data
    folders = user_data.get('folders', {'Папка1': []})
    active_folder = user_data.get('active_folder', 'Папка1')
    channels = folders.get(active_folder, [])
    time_limit = user_data.get('time_limit', DEFAULT_NEWS_TIME_LIMIT_HOURS)
    max_posts = user_data.get('max_posts', DEFAULT_MAX_SUMMARY_POSTS)

    if not channels:
        message_text = (
            "📭 У вас нет добавленных каналов\n"
            "Используйте кнопку '➕ Добавить канал'\n"
            "Для добавления каналов."
        )
        if processing_msg:
            await processing_msg.edit_text(message_text)
        elif query:
            await query.message.reply_text(message_text)
        else:
            await update.message.reply_text(message_text)
        return

    # Increment the request counter (single save instead of load+save)
    if user_id_str in data:
        data[user_id_str]['last_news_date'] = today
        data[user_id_str]['news_request_count'] = news_request_count + 1
        await save_user_data(data)
    remaining -= 1

    # Send initial message or update processing message
    status_text = (
        f"📭 Собираю новости из {len(channels)} каналов (📁 {active_folder})\n"
        f"🕐 За последние {time_limit} часа(ов)\n"
        f"🆕 Количество новостей {max_posts}\n"
    )

    if processing_msg:
        await processing_msg.edit_text(status_text)
        status_message = processing_msg
    elif query:
        status_message = await query.message.reply_text(status_text)
    else:
        status_message = await update.message.reply_text(status_text)

    try:
        # Step 1: Scrape all channels concurrently
        scraping_tasks = [scrape_channel(channel, time_limit) for channel in channels]
        channel_posts = await asyncio.gather(*scraping_tasks)

        # Flatten the list of posts
        all_posts = []
        for posts in channel_posts:
            all_posts.extend(posts)

        if not all_posts:
            if len(channels) == 1:
                await status_message.edit_text(
                    "This channel has no news for your time period."
                )
            else:
                await status_message.edit_text(
                    f"❌ Не найдено новостей за последние {time_limit} часа(ов).\n\n"
                    f"Возможные причины:\n"
                    f"• Каналы не публиковали новости за этот период\n"
                    f"• Каналы закрыты или недоступны\n"
                    f"• Посты слишком короткие (менее 50 символов)\n\n"
                    f"💡 Попробуйте увеличить временной период в настройках ⚙️"
                )
            return

        await status_message.edit_text(
            f"🔍 Найдено {len(all_posts)} поста(ов)\n"
            f"📊 Анализирую и группирую похожие новости ..."
        )

        # Step 2: Cluster similar posts (async to avoid blocking)
        clusters = await cluster_posts(all_posts)

        # Sort clusters by size (most covered stories first)
        clusters.sort(key=len, reverse=True)

        # Show clustering results
        await status_message.edit_text(
            f"⭐️ Количество уникальных новостей: {len(clusters)} из {len(all_posts)}\n"
            f"🔥 Только для Вас! Самые интересные новости\n"
            f"⏳ Процесс создания новостей обычно занимает 10 секунд ...\n"
        )

        # Brief pause before starting progress bar
        await asyncio.sleep(1)

        # Step 3: Summarize clusters in parallel
        clusters_to_process = clusters[:max_posts]

        # Process all clusters in parallel
        summary_tasks = [summarize_cluster(cluster) for cluster in clusters_to_process]
        all_summaries = await asyncio.gather(*summary_tasks)

        # Filter out failed summaries (those without headlines)
        summaries = [s for s in all_summaries if s and s.get('headline')]

        logger.info(f"/news command for user {user_id} found {len(clusters)} stories from {len(all_posts)} posts.")

        # Step 4: Format and send results
        if not summaries:
            await status_message.edit_text(
                "⚠️ Не удалось обработать новости. Попробуйте позже."
            )
            return

        await status_message.delete()

        # Send header
        header = (
            f"📰 Дайджест новостей\n"
            f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
            f"🔥 {len(summaries)} уникальных новостей для Вас! Собраны из {len(channels)} каналов\n"
        )

        if query:
            await query.message.reply_text(header)
        else:
            await update.message.reply_text(header)

        # Send each summary
        for idx, summary in enumerate(summaries, 1):
            coverage_emoji = "🔥" if summary['count'] > 3 else "📰"

            # Escape special Markdown characters in dynamic content
            def escape_markdown(text):
                """Escape special characters for Telegram MarkdownV2."""
                special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
                for char in special_chars:
                    text = text.replace(char, '\\' + char)
                return text

            headline_escaped = escape_markdown(summary['headline'])
            summary_escaped = escape_markdown(summary['summary'])

            # Create clickable links for sources
            post_links = summary.get('post_links', [])
            if post_links:
                # Create markdown links: [channel](url)
                links_text = []
                for link in post_links[:5]:  # Limit to first 5 links to avoid cluttering
                    channel_escaped = escape_markdown(link['channel'])
                    url_escaped = escape_markdown(link['url'])
                    links_text.append(f"[{channel_escaped}]({url_escaped})")

                sources_line = ", ".join(links_text)
                if len(post_links) > 5:
                    sources_line += f" и еще {len(post_links) - 5}"
            else:
                # Fallback to channel names without links
                channels_text = ", ".join(summary['channels'][:3])
                if len(summary['channels']) > 3:
                    channels_text += f" и еще {len(summary['channels']) - 3}"
                sources_line = escape_markdown(channels_text)

            message = (
                f"{coverage_emoji} *{idx}\\. {headline_escaped}*\n\n"
                f"{summary_escaped}\n\n"
                f"_Источники \\({summary['count']}\\): {sources_line}_\n"
            )

            try:
                if query:
                    await query.message.reply_text(message, parse_mode='MarkdownV2')
                else:
                    await update.message.reply_text(message, parse_mode='MarkdownV2')
            except Exception as e:
                # Fallback to plain text if markdown parsing fails
                channels_text = ", ".join(summary['channels'][:3])
                if len(summary['channels']) > 3:
                    channels_text += f" и еще {len(summary['channels']) - 3}"

                message_plain = (
                    f"{coverage_emoji} {idx}. {summary['headline']}\n\n"
                    f"{summary['summary']}\n\n"
                    f"Источники ({summary['count']}): {channels_text}\n"
                )
                if query:
                    await query.message.reply_text(message_plain)
                else:
                    await update.message.reply_text(message_plain)

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        # Send return to menu button without separator
        reply_markup = create_return_menu_button()
        if query:
            await query.message.reply_text("Выберите действие:", reply_markup=reply_markup)
        else:
            await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in news_command for user {user_id}: {str(e)}", exc_info=True)
        error_text = "😕 Извините, что-то пошло не так. Попробуйте позже."
        if query:
            await query.message.reply_text(error_text)
        else:
            await update.message.reply_text(error_text)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - fetch, deduplicate, and summarize news."""
    await news_command_internal(update, context)


async def send_form_to_admin(context: ContextTypes.DEFAULT_TYPE, form_type: str, form_data: dict):
    """Send form submission to admin via Telegram."""
    if not ADMIN_CHAT_ID:
        logger.error("ADMIN_CHAT_ID not set in environment variables")
        return False

    try:
        if form_type == "add_to_feed":
            message = (
                f"📝 Новая заявка: Добавить канал в ленту\n\n"
                f"👤 От пользователя: {form_data['user_id']} (@{form_data['username']})\n"
                f"📢 Канал: {form_data['channel']}\n"
                f"🏷️ Хештег: {form_data['hashtag']}\n"
                f"📝 Описание: {form_data['description']}\n"
                f"🕐 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        elif form_type == "remove_from_feed":
            message = (
                f"📝 Новая заявка: Удалить канал из ленты\n\n"
                f"👤 От пользователя: {form_data['user_id']} (@{form_data['username']})\n"
                f"📢 Канал: {form_data['channel']}\n"
                f"❓ Причина: {form_data.get('reason', 'Не указана')}\n"
                f"🕐 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        elif form_type == "restrict_access":
            message = (
                f"📝 Новая заявка: Ограничить доступ\n\n"
                f"👤 От пользователя: {form_data['user_id']} (@{form_data['username']})\n"
                f"📢 Канал: {form_data['channel']}\n"
                f"❓ Причина: {form_data.get('reason', 'Не указана')}\n"
                f"🕐 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
            )
        else:
            return False

        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        return True
    except Exception as e:
        logger.error(f"Error sending form to admin: {e}", exc_info=True)
        return False


# Handler functions for "Add channel to feed" form
async def handle_add_to_feed_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for add to feed form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_ADD_TO_FEED_CHANNEL

    # Validate channel accessibility (same as main Add Channel feature)
    is_valid, error_msg = await validate_channel_access(channel, update)

    if not is_valid:
        logger.warning(f"User {user_id} tried to add inaccessible channel {channel}: {error_msg}")
        return WAITING_FOR_ADD_TO_FEED_CHANNEL

    # Store channel in context
    context.user_data['form_channel'] = channel
    user_logger.info(f"User_{user_id} (@{username}) entered channel {channel} for add to feed")

    # Get user's Telegram username and auto-fill
    if not await validate_and_store_username(update, context):
        return ConversationHandler.END

    owner_name = context.user_data['form_owner_name']

    # Show confirmation message and proceed to hashtag selection
    reply_markup = create_hashtag_keyboard()
    await update.message.reply_text(
        f"Ваше имя ({owner_name}) должно совпадать с именем в описании канала, иначе мы не сможем рассмотреть вашу заявку!\n\n"
        f"Выберите хештег для вашего канала:",
        reply_markup=reply_markup
    )
    return WAITING_FOR_ADD_TO_FEED_HASHTAG


async def handle_add_to_feed_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle description input for add to feed form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    description = update.message.text.strip()

    # Validate description length
    if len(description) > 30:
        await update.message.reply_text(
            f"❌ Описание слишком длинное ({len(description)} символов)\n"
            f"Максимум: 30 символов\n\n"
            f"Попробуйте еще раз:"
        )
        return WAITING_FOR_ADD_TO_FEED_DESCRIPTION

    if len(description) < 5:
        await update.message.reply_text(
            "❌ Описание слишком короткое (минимум 5 символов)\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_ADD_TO_FEED_DESCRIPTION

    # Store description in context
    context.user_data['form_description'] = description
    user_logger.info(f"User_{user_id} (@{username}) entered description for add to feed")

    # Prepare form data
    form_data = {
        'user_id': user_id,
        'username': username,
        'channel': context.user_data.get('form_channel'),
        'hashtag': context.user_data.get('form_hashtag'),
        'description': description
    }

    # Send form to admin
    success = await send_form_to_admin(context, "add_to_feed", form_data)

    if success:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "✅ Ваша заявка отправлена на рассмотрение!\n\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=reply_markup
        )
    else:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке заявки.\n"
            "Попробуйте позже или свяжитесь с нами: @fast_news_ai_admin",
            reply_markup=reply_markup
        )

    # Clear form data
    context.user_data.clear()
    return ConversationHandler.END


# Handler functions for "Remove channel from feed" form
async def handle_remove_from_feed_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for remove from feed form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_REMOVE_FROM_FEED_CHANNEL

    # Check if channel is in feed
    if not await check_channel_in_feed(channel):
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            f"❌ Канал {channel} не найден в ленте.",
            reply_markup=reply_markup
        )
        context.user_data.clear()
        return ConversationHandler.END

    # Store channel in context
    context.user_data['form_channel'] = channel
    user_logger.info(f"User_{user_id} (@{username}) entered channel {channel} for remove from feed")

    # Get user's Telegram username and auto-fill
    if not await validate_and_store_username(update, context):
        return ConversationHandler.END

    owner_name = context.user_data['form_owner_name']

    # Show confirmation message and proceed to reason
    await update.message.reply_text(
        f"✅ Канал: {channel}\n\n"
        f"Ваше имя ({owner_name}) должно совпадать с именем в описании канала, иначе мы не сможем обработать вашу заявку!\n\n"
        f"Укажите причину (необязательно):\n"
        f"Или введите 'пропустить' чтобы пропустить этот шаг."
    )
    return WAITING_FOR_REMOVE_FROM_FEED_REASON


async def handle_remove_from_feed_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reason input for remove from feed form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    reason = update.message.text.strip()

    # Check if user wants to skip
    if reason.lower() in ['пропустить', 'skip']:
        reason = None

    user_logger.info(f"User_{user_id} (@{username}) entered reason for remove from feed")

    # Prepare form data
    form_data = {
        'user_id': user_id,
        'username': username,
        'channel': context.user_data.get('form_channel'),
        'reason': reason
    }

    # Send form to admin
    success = await send_form_to_admin(context, "remove_from_feed", form_data)

    if success:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "✅ Ваша заявка отправлена на рассмотрение!\n\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=reply_markup
        )
    else:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке заявки.\n"
            "Попробуйте позже или свяжитесь с нами: @fast_news_ai_admin",
            reply_markup=reply_markup
        )

    # Clear form data
    context.user_data.clear()
    return ConversationHandler.END


# Handler functions for "Restrict Access" form
async def handle_restrict_access_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for restrict access form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_RESTRICT_ACCESS_CHANNEL

    # Validate channel accessibility (same as main Add Channel feature)
    is_valid, error_msg = await validate_channel_access(channel, update)

    if not is_valid:
        logger.warning(f"User {user_id} tried to add inaccessible channel {channel}: {error_msg}")
        return WAITING_FOR_RESTRICT_ACCESS_CHANNEL

    # Store channel in context
    context.user_data['form_channel'] = channel
    user_logger.info(f"User_{user_id} (@{username}) entered channel {channel} for restrict access")

    # Get user's Telegram username and auto-fill
    if not await validate_and_store_username(update, context):
        return ConversationHandler.END

    owner_name = context.user_data['form_owner_name']

    # Show confirmation message and proceed to reason
    await update.message.reply_text(
        f"Ваше имя ({owner_name}) должно совпадать с именем в описании канала, иначе мы не сможем рассмотреть вашу заявку!\n\n"
        f"Укажите причину (необязательно):\n"
        f"Или введите 'пропустить' чтобы пропустить этот шаг."
    )
    return WAITING_FOR_RESTRICT_ACCESS_REASON


async def handle_restrict_access_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle reason input for restrict access form."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    reason = update.message.text.strip()

    # Check if user wants to skip
    if reason.lower() in ['пропустить', 'skip']:
        reason = None

    user_logger.info(f"User_{user_id} (@{username}) entered reason for restrict access")

    # Prepare form data
    form_data = {
        'user_id': user_id,
        'username': username,
        'channel': context.user_data.get('form_channel'),
        'reason': reason
    }

    # Send form to admin
    success = await send_form_to_admin(context, "restrict_access", form_data)

    if success:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "✅ Ваша заявка отправлена на рассмотрение!\n\n"
            "Мы свяжемся с вами в ближайшее время.",
            reply_markup=reply_markup
        )
    else:
        reply_markup = create_return_menu_button()
        await update.message.reply_text(
            "❌ Произошла ошибка при отправке заявки.\n"
            "Попробуйте позже или свяжитесь с нами: @fast_news_ai_admin",
            reply_markup=reply_markup
        )

    # Clear form data
    context.user_data.clear()
    return ConversationHandler.END


def main():
    """Start the bot."""
    logger.info("Starting bot...")

    # Create application
    application = (
        Application.builder()
        .token(TELEGRAM_BOT_API)
        .post_shutdown(close_http_client)
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
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("restore_backup", restore_backup_command))
    application.add_handler(conv_handler)

    # Keep old command handlers for backward compatibility
    application.add_handler(CommandHandler("add", add_channel))
    application.add_handler(CommandHandler("remove", remove_channel))
    application.add_handler(CommandHandler("remove_all", remove_all_channels))
    application.add_handler(CommandHandler("list", list_channels))
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
