# -*- coding: utf-8 -*-
"""News command handler."""

import asyncio
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ContextTypes

from bot.utils.config import MAX_NEWS_REQUESTS_PER_DAY, DEFAULT_NEWS_TIME_LIMIT_HOURS, DEFAULT_MAX_SUMMARY_POSTS
from bot.utils.logger import setup_logging
from bot.services import (
    StorageService,
    AIService,
    ScraperService,
    ClusteringService,
    messenger as messenger_service,
)

# Setup logging
logger, user_logger = setup_logging()


def create_return_menu_button():
    """Import to avoid circular dependency."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = [
        [InlineKeyboardButton("🏠 Вернуться в меню", callback_data='return_to_menu')]
    ]
    return InlineKeyboardMarkup(keyboard)


async def news_command_internal(update: Update, context: ContextTypes.DEFAULT_TYPE, processing_msg=None):
    """Internal news command handler that works with both command and button."""
    storage = StorageService()
    ai_service = AIService()
    scraper = ScraperService()
    clustering = ClusteringService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    chat_id = update.effective_chat.id

    logger.info(f"User {user_id} ran /news command.")
    user_logger.info(f"User_{user_id} (@{username}) clicked /news")

    # Load user data once to avoid multiple redundant loads
    data = await storage.load_user_data()
    user_id_str = str(user_id)
    user_data = data.get(user_id_str, {})

    # Check rate limit (inline to avoid extra load)
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    last_news_date = user_data.get('last_news_date', '')
    news_request_count = user_data.get('news_request_count', 0)

    if last_news_date != today:
        news_request_count = 0

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
        else:
            await messenger_service.send_text(chat_id, message_text)
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
        else:
            await messenger_service.send_text(chat_id, message_text)
        return

    # Increment the request counter (single save instead of load+save)
    if user_id_str in data:
        data[user_id_str]['last_news_date'] = today
        data[user_id_str]['news_request_count'] = news_request_count + 1
        await storage.save_user_data(data)

    # Send initial message or update processing message
    status_text = (
        f"📭 Собираю новости из {len(channels)} каналов (📁 {active_folder})\n"
        f"🕐 За последние {time_limit} часа(ов)\n"
        f"🆕 Количество новостей {max_posts}\n"
    )

    if processing_msg:
        await processing_msg.edit_text(status_text)
        status_message = processing_msg
    else:
        status_message = await messenger_service.send_text(chat_id, status_text)

    try:
        # Step 1: Scrape all channels concurrently
        scraping_tasks = [scraper.scrape_channel(channel, time_limit) for channel in channels]
        channel_posts = await asyncio.gather(*scraping_tasks)

        # Flatten the list of posts
        all_posts = []
        for posts in channel_posts:
            all_posts.extend(posts)

        if not all_posts:
            if len(channels) == 1:
                await status_message.edit_text(
                    "На этом канале(ах) нет новостей за ваш временной период."
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
        texts = [post['text'] for post in all_posts]
        embeddings = await ai_service.get_embeddings(texts)
        clusters = clustering.cluster_posts(embeddings, all_posts)

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
        summary_tasks = [ai_service.summarize_cluster(cluster) for cluster in clusters_to_process]
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

        await messenger_service.send_text(chat_id, header)

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
                await messenger_service.send_text(chat_id, message, parse_mode='MarkdownV2')
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
                await messenger_service.send_text(chat_id, message_plain)

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.5)

        # Send return to menu button without separator
        reply_markup = create_return_menu_button()
        await messenger_service.send_text(chat_id, "Выберите действие:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Error in news_command for user {user_id}: {str(e)}", exc_info=True)
        error_text = "😕 Извините, что-то пошло не так. Попробуйте позже."
        await messenger_service.send_text(chat_id, error_text)


async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /news command - fetch, deduplicate, and summarize news."""
    await news_command_internal(update, context)
