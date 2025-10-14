# -*- coding: utf-8 -*-
"""Configuration module for the bot.

Contains all constants, environment variables, and configuration settings.
"""
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Suppress gRPC warnings - must be set BEFORE importing google libraries
os.environ['GRPC_VERBOSITY'] = 'NONE'
os.environ['GLOG_minloglevel'] = '2'
os.environ['GRPC_ENABLE_FORK_SUPPORT'] = '0'
os.environ['GRPC_POLL_STRATEGY'] = 'poll'

# Environment variables
TELEGRAM_BOT_API: str = os.getenv('TELEGRAM_BOT_API')
GEMINI_API: str = os.getenv('GEMINI_API')
ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID')  # Admin's Telegram chat ID for receiving forms

# File paths
USER_DATA_FILE: str = 'user_data.json'
CHANNEL_FEED_FILE: str = 'channel_feed.json'
USER_DATA_BACKUP_DIR: str = os.path.join('backups', 'user_data')

# Backup settings
MAX_BACKUP_COUNT: int = 20
BACKUP_RETENTION_DAYS: int = 7

# Admin chat ID validation
ADMIN_CHAT_ID_INT: int = None
try:
    ADMIN_CHAT_ID_INT = int(ADMIN_CHAT_ID) if ADMIN_CHAT_ID else None
except ValueError:
    # Logger not yet initialized, will be logged later
    ADMIN_CHAT_ID_INT = None

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
