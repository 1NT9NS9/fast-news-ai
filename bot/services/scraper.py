# -*- coding: utf-8 -*-
"""
Scraper Service

Handles all web scraping operations for Telegram channels:
- Channel post scraping from public preview pages
- Channel validation and access checking
- Subscriber count parsing
- HTTP client management with connection pooling
"""

import re
import asyncio
import httpx
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from telegram import Update

from bot.utils.config import MAX_POSTS_PER_CHANNEL, DEFAULT_NEWS_TIME_LIMIT_HOURS
from bot.utils.logger import setup_logging
from bot.utils.validators import validate_channel_name, validate_scrape_url

logger, _ = setup_logging()


class ScraperService:
    """Manages web scraping operations for Telegram channels."""

    def __init__(self):
        # Shared HTTP client with connection pooling
        self._http_client: Optional[httpx.AsyncClient] = None
        self._http_client_lock = asyncio.Lock()

        # Scraping configuration
        self.base_url = "https://t.me/s/"
        self.timeout = 30.0
        self.validation_timeout = 10.0

    # ========================================================================
    # HTTP Client Management
    # ========================================================================

    async def get_http_client(self) -> httpx.AsyncClient:
        """Return a shared HTTP client with connection pooling."""
        if self._http_client is None:
            async with self._http_client_lock:
                if self._http_client is None:
                    self._http_client = httpx.AsyncClient(
                        follow_redirects=True,
                        timeout=self.timeout
                    )
        return self._http_client

    async def close_http_client(self) -> None:
        """Close the shared HTTP client if it was created."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    # ========================================================================
    # Channel Validation
    # ========================================================================

    async def validate_channel_access(self, channel: str, update: Update) -> Tuple[bool, Optional[str]]:
        """
        Validate that a Telegram channel is accessible.

        Args:
            channel: Channel name (with or without @)
            update: Telegram Update object

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        try:
            canonical_channel = validate_channel_name(channel)
            scrape_url = validate_scrape_url(canonical_channel)
        except ValueError as exc:
            logger.info("Rejected channel during validation: %s", exc)
            if update.message:
                await update.message.reply_text(
                    "Неверный формат канала. Используйте публичный Telegram ID вида @example."
                )
            return False, str(exc)

        validation_msg = await update.message.reply_text(
            f"🔍 Проверяю доступность канала {canonical_channel}..."
        )

        try:
            client = await self.get_http_client()
            response = await client.get(scrape_url, timeout=self.validation_timeout)
            response.raise_for_status()

            if "tgme_channel_info" not in response.text and \
               "tgme_widget_message" not in response.text:
                await validation_msg.edit_text(
                    f"❌ Не удалось получить доступ к {canonical_channel}. "
                    "Канал может быть приватным или не существует."
                )
                return False, "Channel not accessible"

            await validation_msg.edit_text(f"✅ Канал {canonical_channel} проверен и доступен!")
            return True, None

        except httpx.HTTPStatusError as e:
            logger.warning(f"Channel validation failed: HTTP {e.response.status_code}")
            await validation_msg.edit_text(
                f"❌ Не удалось получить доступ к {canonical_channel}. "
                "Канал может быть приватным или не существует."
            )
            return False, f"HTTP {e.response.status_code}"

        except Exception as e:
            logger.error(f"Error validating channel: {e}", exc_info=True)
            await validation_msg.edit_text(
                "😕 Произошла ошибка при проверке канала. Попробуйте позже."
            )
            return False, str(e)

    # ========================================================================
    # Subscriber Count Parsing
    # ========================================================================

    def parse_subscriber_count(self, text: str) -> int:
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

    # ========================================================================
    # Channel Scraping
    # ========================================================================

    async def scrape_channel(self, channel_name: str, time_limit_hours: int = DEFAULT_NEWS_TIME_LIMIT_HOURS) -> List[Dict]:
        """
        Scrape recent posts from a public Telegram channel.

        Args:
            channel_name: Channel name (e.g., '@channelname')
            time_limit_hours: Only include posts from the last N hours

        Returns:
            List of dictionaries with post data including:
            - text: Full text content of the post
            - channel: Channel name with @ prefix
            - url: Direct URL to the post (e.g., https://t.me/channel/123)
            - timestamp: Publication time as datetime object (timezone-aware)
            - subscriber_count: Total subscriber count for the channel
        """
        try:
            canonical_channel = validate_channel_name(channel_name)
            scrape_url = validate_scrape_url(canonical_channel)
        except ValueError as exc:
            logger.info("Rejected channel scraping request: %s", exc)
            return []

        posts = []

        # Calculate time cutoff (timezone-aware)
        time_cutoff = datetime.now(timezone.utc) - timedelta(hours=time_limit_hours)

        try:
            http_client = await self.get_http_client()
            response = await http_client.get(scrape_url, timeout=self.timeout)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract channel subscriber count
            subscriber_count = 0
            subscriber_elem = soup.find('div', class_='tgme_channel_info_counter')
            if subscriber_elem:
                subscriber_text = subscriber_elem.get_text(strip=True)
                subscriber_count = self.parse_subscriber_count(subscriber_text)
                logger.debug(f"Channel {canonical_channel} has {subscriber_count} subscribers")

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
                            logger.debug(f"Assuming UTC for naive timestamp in {canonical_channel}: {post_time_str}")
                            post_time = post_time.replace(tzinfo=timezone.utc)

                        # Store the datetime object for future use (timezone-aware)
                        post_timestamp = post_time

                        # Skip posts older than time limit (compare timezone-aware datetimes)
                        if post_timestamp < time_cutoff:
                            logger.debug(f"Skipping old post from {canonical_channel}: {post_timestamp} (cutoff: {time_cutoff})")
                            continue
                    except Exception as e:
                        logger.warning(f"Could not parse timestamp for post in {canonical_channel}: {e}")
                        # Skip posts with unparseable timestamps to enforce time filter
                        continue

                if not post_timestamp:
                    logger.debug(f"Skipping post without timestamp from {canonical_channel}")
                    continue

                posts.append({
                    'text': text,
                    'channel': canonical_channel,
                    'url': post_url,
                    'timestamp': post_timestamp,
                    'subscriber_count': subscriber_count
                })
                post_count += 1

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Channel {canonical_channel} not found (404)")
            else:
                logger.warning(f"HTTP error scraping {canonical_channel}: {e.response.status_code}")
        except httpx.TimeoutException:
            logger.error(f"Timeout while scraping {canonical_channel}")
        except Exception as e:
            logger.error(f"Error scraping {canonical_channel}: {str(e)}", exc_info=True)

        return posts
