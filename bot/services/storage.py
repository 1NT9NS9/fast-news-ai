# -*- coding: utf-8 -*-
"""
Storage Service

Handles all file I/O operations for user data and channel feeds:
- User data caching and persistence
- Backup management (creation, rotation, cleanup, restore)
- Channel management per user
- Rate limiting tracking
"""

import os
import shutil
import json
import asyncio
import aiofiles
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Tuple

from bot.utils.config import (
    USER_DATA_FILE, CHANNEL_FEED_FILE, USER_DATA_BACKUP_DIR,
    MAX_BACKUP_COUNT, BACKUP_RETENTION_DAYS,
    DEFAULT_NEWS_TIME_LIMIT_HOURS, DEFAULT_MAX_SUMMARY_POSTS,
    MAX_NEWS_REQUESTS_PER_DAY
)
from bot.utils.logger import setup_logging
from bot.models.user_data import migrate_user_data_to_folders, validate_user_data

logger, _ = setup_logging()


class StorageService:
    """Manages user data storage, caching, and backups."""

    def __init__(self):
        # In-memory cache for user data to reduce file I/O
        self._user_data_cache: Optional[Dict] = None
        self._cache_lock = asyncio.Lock()

        # Cache for user channels (across all folders)
        self._user_channels_cache: Dict[str, Tuple] = {}
        self._user_channels_cache_lock = asyncio.Lock()

        # Backup debouncing - track last backup time to avoid excessive backups
        self._last_backup_time = 0
        self._backup_debounce_seconds = 60  # Max 1 backup per minute

    # ========================================================================
    # User Data - Core Operations
    # ========================================================================

    async def load_user_data(self) -> Dict:
        """Load user data from JSON file with validation and auto-recovery."""
        async with self._cache_lock:
            if self._user_data_cache is not None:
                return self._user_data_cache

            try:
                async with aiofiles.open(USER_DATA_FILE, 'r', encoding='utf-8') as f:
                    raw_content = await f.read()
            except FileNotFoundError:
                self._user_data_cache = {}
                await self._invalidate_user_channel_cache()
                return self._user_data_cache
            except OSError as exc:
                logger.error('Failed to read %s: %s', USER_DATA_FILE, exc)
                self._user_data_cache = {}
                await self._invalidate_user_channel_cache()
                return self._user_data_cache

            try:
                raw_data = json.loads(raw_content)
            except json.JSONDecodeError as exc:
                logger.error('Failed to parse %s: %s', USER_DATA_FILE, exc)
                restored = await self._attempt_auto_restore_user_data('JSON decode error')
                if restored is not None:
                    self._user_data_cache = restored
                    await self._invalidate_user_channel_cache()
                    return restored
                self._user_data_cache = {}
                await self._invalidate_user_channel_cache()
                return self._user_data_cache

            data = migrate_user_data_to_folders(raw_data)
            is_valid, issues = validate_user_data(data)
            if is_valid:
                self._user_data_cache = data
                await self._invalidate_user_channel_cache()
                return data

            logger.error('User data validation failed: %s', '; '.join(issues))
            restored = await self._attempt_auto_restore_user_data('validation failure')
            if restored is not None:
                self._user_data_cache = restored
                await self._invalidate_user_channel_cache()
                return restored

            self._user_data_cache = {}
            await self._invalidate_user_channel_cache()
            return self._user_data_cache

    async def save_user_data(self, data: Dict) -> None:
        """Save user data to JSON file and update cache after validation."""
        async with self._cache_lock:
            is_valid, issues = validate_user_data(data)
            if not is_valid:
                logger.error('Aborting save_user_data due to validation errors: %s', '; '.join(issues))
                raise ValueError('User data failed validation; see logs for details.')

            # Backup BEFORE saving new data to avoid race condition
            if os.path.exists(USER_DATA_FILE):
                await self.backup_user_data()

            self._user_data_cache = data
            serialized = json.dumps(data, indent=2, ensure_ascii=False)
            async with aiofiles.open(USER_DATA_FILE, 'w', encoding='utf-8') as f:
                await f.write(serialized)

    # ========================================================================
    # User Data - Channel Operations
    # ========================================================================

    async def get_user_channels(self, user_id: int) -> List[str]:
        """Get channels for a specific user from their active folder."""
        data = await self.load_user_data()
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

    async def get_active_folder_name(self, user_id: int) -> str:
        """Get the name of the user's active folder."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str in data:
            user_data = data[user_id_str]
            if 'active_folder' in user_data:
                return user_data['active_folder']
        return 'Папка1'

    async def get_all_user_channels(self, user_id: int) -> List[str]:
        """Return all channels across folders for a user, cached for reuse."""
        user_id_str = str(user_id)

        async with self._user_channels_cache_lock:
            cached = self._user_channels_cache.get(user_id_str)
        if cached is not None:
            return list(cached)

        data = await self.load_user_data()
        user_data = data.get(user_id_str)
        channels = self._extract_all_channels(user_data)

        await self._cache_user_channels(user_id_str, channels)
        return channels

    async def set_user_channels(self, user_id: int, channels: List[str]) -> None:
        """Set channels for a specific user in their active folder."""
        data = await self.load_user_data()
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

        await self.save_user_data(data)

        all_channels = self._extract_all_channels(user_data)
        await self._cache_user_channels(user_id_str, all_channels)

    # ========================================================================
    # User Data - Settings Operations
    # ========================================================================

    async def get_user_time_limit(self, user_id: int) -> int:
        """Get news time limit for a specific user."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str in data:
            return data[user_id_str].get('time_limit', DEFAULT_NEWS_TIME_LIMIT_HOURS)
        return DEFAULT_NEWS_TIME_LIMIT_HOURS

    async def set_user_time_limit(self, user_id: int, hours: int) -> None:
        """Set news time limit for a specific user."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str not in data:
            data[user_id_str] = {}
        data[user_id_str]['time_limit'] = hours
        await self.save_user_data(data)

    async def get_user_max_posts(self, user_id: int) -> int:
        """Get max posts limit for a specific user."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str in data:
            return data[user_id_str].get('max_posts', DEFAULT_MAX_SUMMARY_POSTS)
        return DEFAULT_MAX_SUMMARY_POSTS

    async def set_user_max_posts(self, user_id: int, max_posts: int) -> None:
        """Set max posts limit for a specific user."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str not in data:
            data[user_id_str] = {}
        data[user_id_str]['max_posts'] = max_posts
        await self.save_user_data(data)

    # ========================================================================
    # User Data - Folder Operations
    # ========================================================================

    async def get_user_folders(self, user_id: int) -> Dict[str, List[str]]:
        """Get all folders for a user."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str in data and 'folders' in data[user_id_str]:
            return data[user_id_str]['folders']
        return {'Папка1': []}

    async def create_folder(self, user_id: int, folder_name: str) -> bool:
        """Create a new folder for a user. Returns True if successful."""
        data = await self.load_user_data()
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
        await self.save_user_data(data)
        await self._cache_user_channels(user_id_str, self._extract_all_channels(data[user_id_str]))
        return True

    async def delete_folder(self, user_id: int, folder_name: str) -> bool:
        """Delete a folder (and its channels) for a user. Returns True if successful."""
        data = await self.load_user_data()
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

        await self.save_user_data(data)
        await self._cache_user_channels(user_id_str, self._extract_all_channels(data[user_id_str]))
        return True

    async def switch_active_folder(self, user_id: int, folder_name: str) -> bool:
        """Switch the user's active folder. Returns True if successful."""
        data = await self.load_user_data()
        user_id_str = str(user_id)
        if user_id_str not in data or 'folders' not in data[user_id_str]:
            return False

        if folder_name not in data[user_id_str]['folders']:
            return False

        data[user_id_str]['active_folder'] = folder_name
        await self.save_user_data(data)
        return True

    # ========================================================================
    # User Data - Rate Limiting
    # ========================================================================

    async def check_news_rate_limit(self, user_id: int) -> Tuple[bool, int]:
        """
        Check if user has exceeded daily news request limit.

        Returns:
            tuple: (is_allowed, remaining_requests)
        """
        data = await self.load_user_data()
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
            await self.save_user_data(data)

        request_count = user_data.get('news_request_count', 0)
        remaining = MAX_NEWS_REQUESTS_PER_DAY - request_count

        return (request_count < MAX_NEWS_REQUESTS_PER_DAY, remaining)

    async def increment_news_request(self, user_id: int) -> None:
        """Increment the news request counter for a user."""
        data = await self.load_user_data()
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
        await self.save_user_data(data)

    # ========================================================================
    # Channel Feed Operations
    # ========================================================================

    async def load_channel_feed(self) -> Dict:
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

    async def save_channel_feed(self, data: Dict) -> None:
        """Save channel feed data to JSON file."""
        serialized = json.dumps(data, indent=2, ensure_ascii=False)
        async with aiofiles.open(CHANNEL_FEED_FILE, 'w', encoding='utf-8') as f:
            await f.write(serialized)

    async def check_channel_in_feed(self, channel_name: str) -> bool:
        """Check if a channel is in the feed."""
        feed_data = await self.load_channel_feed()
        return channel_name in feed_data

    # ========================================================================
    # Backup Operations
    # ========================================================================

    async def backup_user_data(self) -> None:
        """Asynchronously back up the current user data state with debouncing."""
        current_time = datetime.now().timestamp()
        time_since_last_backup = current_time - self._last_backup_time

        # Skip backup if less than debounce period has passed
        if time_since_last_backup < self._backup_debounce_seconds:
            logger.debug(f"Skipping backup (last backup {time_since_last_backup:.1f}s ago, debounce: {self._backup_debounce_seconds}s)")
            return

        # Update last backup time and perform backup
        self._last_backup_time = current_time
        await asyncio.to_thread(self._perform_user_data_backup)

    def _perform_user_data_backup(self) -> None:
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

        self._cleanup_old_backups()

    def _cleanup_old_backups(self) -> None:
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

    def list_user_data_backups(self) -> List[Dict]:
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

    async def restore_user_data_from_backup(self, backup_path: str) -> Dict:
        """Restore user data from a selected backup file."""
        async with self._cache_lock:
            await self.backup_user_data()
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

            self._user_data_cache = restored_data
            await self._invalidate_user_channel_cache()

        logger.info('User data restored from backup %s', backup_path)
        return restored_data

    async def _attempt_auto_restore_user_data(self, reason: str) -> Optional[Dict]:
        """Attempt to auto-restore user data from the newest valid backup."""
        backups = self.list_user_data_backups()
        if not backups:
            logger.error('Unable to auto-restore user data (%s): no backups found.', reason)
            return None

        await self.backup_user_data()

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

    # ========================================================================
    # Internal Helper Methods
    # ========================================================================

    async def _invalidate_user_channel_cache(self, user_id: Optional[int] = None) -> None:
        """Clear cached channel lists either globally or for a specific user."""
        async with self._user_channels_cache_lock:
            if user_id is None:
                self._user_channels_cache.clear()
            else:
                self._user_channels_cache.pop(str(user_id), None)

    async def _cache_user_channels(self, user_id_str: str, channels: List[str]) -> None:
        """Store a snapshot of a user's channels for quick reuse."""
        async with self._user_channels_cache_lock:
            self._user_channels_cache[user_id_str] = tuple(channels)

    def _extract_all_channels(self, user_data: Optional[Dict]) -> List[str]:
        """Return a deduplicated list of all channels from the user data."""
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
