# -*- coding: utf-8 -*-
"""Configuration module for the bot.

Contains all constants, environment variables, and configuration settings.
"""
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
logger = logging.getLogger(__name__)


def _get_int_env(name: str, default: int) -> int:
    """Return integer environment variables with a safe fallback."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        logger.warning("Invalid integer for %s: %s. Using default %s.", name, raw_value, default)
        return default

# Suppress gRPC warnings - must be set BEFORE importing google libraries
os.environ['GRPC_VERBOSITY'] = 'NONE'
os.environ['GLOG_minloglevel'] = '2'
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'

# Environment variables
TELEGRAM_BOT_API: str = os.getenv('TELEGRAM_BOT_API')
GEMINI_API: str = os.getenv('GEMINI_API')
ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID')  # Admin's Telegram chat ID for receiving forms
ADMIN_CHAT_ID_BACKUP: str = os.getenv('ADMIN_CHAT_ID_BACKUP')  # Admin's chat ID for backup restoration
ADMIN_CHAT_ID_LOG: str = os.getenv('ADMIN_CHAT_ID_LOG')  # Admin's chat ID for receiving log messages
GEMINI_EMBEDDING_MODEL: str = os.getenv('GEMINI_EMBEDDING_MODEL', 'gemini-embedding-001')
EMBEDDING_TASK_TYPE: str = os.getenv('EMBEDDING_TASK_TYPE', 'retrieval_document')
EMBEDDING_OUTPUT_DIM: int = _get_int_env('EMBEDDING_OUTPUT_DIM', 768)
EMBEDDING_TEXTS_PER_BATCH: int = _get_int_env('EMBEDDING_TEXTS_PER_BATCH', 50)
EMBEDDING_RPM: int = _get_int_env('EMBEDDING_RPM', 3000)
EMBEDDING_MAX_TOKENS: int = _get_int_env('EMBEDDING_MAX_TOKENS', 400)
GEMINI_EMBEDDING_CONCURRENT_LIMIT: int = _get_int_env('GEMINI_EMBEDDING_CONCURRENT_LIMIT', 32)

# File paths
USER_DATA_FILE: str = 'user_data.json'
CHANNEL_FEED_FILE: str = 'channel_feed.json'
PLAN_SUBSCRIPTIONS_FILE: str = 'plan_subscriptions.json'
USER_DATA_BACKUP_DIR: str = os.path.join('backups', 'user_data')

# Backup settings
BACKUP_DEBOUNCE_SECONDS: int = 60  # Minimum interval between backups (in seconds)
MAX_BACKUP_COUNT: int = 20
BACKUP_RETENTION_DAYS: int = 7

# Admin chat ID validation
ADMIN_CHAT_ID_INT: int = None
ADMIN_CHAT_ID_BACKUP_INT: int = None
ADMIN_CHAT_ID_LOG_INT: int = None

try:
    ADMIN_CHAT_ID_INT = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None
except ValueError:
    # Logger not yet initialized, will be logged later
    ADMIN_CHAT_ID_INT = None

try:
    ADMIN_CHAT_ID_BACKUP_INT = int(ADMIN_CHAT_ID_BACKUP) if ADMIN_CHAT_ID_BACKUP else None
except ValueError:
    ADMIN_CHAT_ID_BACKUP_INT = None

try:
    ADMIN_CHAT_ID_LOG_INT = int(ADMIN_CHAT_ID_LOG) if ADMIN_CHAT_ID_LOG else None
except ValueError:
    ADMIN_CHAT_ID_LOG_INT = None

# Bot limits and constraints
MAX_CHANNELS: int = 10
MAX_POSTS_PER_CHANNEL: int = 20
DEFAULT_NEWS_TIME_LIMIT_HOURS: int = 24  # Default time range for news
MAX_NEWS_TIME_LIMIT_HOURS: int = 720  # Maximum allowed time range (30 days)
DEFAULT_MAX_SUMMARY_POSTS: int = 10  # Default number of news summaries
MAX_SUMMARY_POSTS_LIMIT: int = 30  # Maximum allowed summaries
MAX_NEWS_REQUESTS_PER_DAY: int = 5  # Rate limit for /news command

# AI/Clustering settings
SIMILARITY_THRESHOLD: float = 0.9
GEMINI_API_RATE_LIMIT: int = 4000  # Gemini API rate limit: 4000 requests per minute
GEMINI_CONCURRENT_LIMIT: int = 4000  # Max concurrent Gemini API requests
