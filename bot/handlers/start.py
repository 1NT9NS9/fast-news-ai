# -*- coding: utf-8 -*-
"""Start command handler."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes

from bot.utils.config import DEFAULT_NEWS_TIME_LIMIT_HOURS, DEFAULT_MAX_SUMMARY_POSTS
from bot.utils.logger import setup_logging
from bot.services import StorageService
from bot.services import messenger as messenger_service

# Setup logging
logger, user_logger = setup_logging()


async def _send_reply(
    update: Update,
    text: str,
    *,
    reply_markup=None,
    reply: bool = False,
    **kwargs,
):
    """Send a reply via the rate-limited messenger wrapper."""
    chat = update.effective_chat
    if chat is None:
        raise RuntimeError("Cannot send message without an active chat.")
    send_kwargs = dict(kwargs)
    if reply_markup is not None:
        send_kwargs["reply_markup"] = reply_markup
    if reply and update.message is not None:
        send_kwargs.setdefault("reply_to_message_id", update.message.message_id)
    return await messenger_service.send_text(chat.id, text, **send_kwargs)


def create_persistent_keyboard():
    """Create the persistent keyboard with a single 'Return to menu' button."""
    keyboard = [
        [KeyboardButton("🏠 Вернуться в меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)


def create_main_menu():
    """Create the main menu keyboard with folder management."""
    keyboard = [
        [InlineKeyboardButton("✨ Начать", callback_data='start_plans')],
        [InlineKeyboardButton("📰 Получить новости", callback_data='get_news')],
        [InlineKeyboardButton("📁 Управление папками", callback_data='manage_folders')],
        [InlineKeyboardButton("➕ Добавить канал", callback_data='add_channel'), InlineKeyboardButton("➖ Удалить канал", callback_data='remove_channel')],
        [InlineKeyboardButton("📋 Список каналов", callback_data='list_channels')],
        [InlineKeyboardButton("⏰ Время", callback_data='time_interval'), InlineKeyboardButton("📊 Новости", callback_data='news_count')],
        [InlineKeyboardButton("🔥Лента новостей", callback_data='news_feed')],
        [InlineKeyboardButton("⭐️ Для владельцев каналов", callback_data='for_channel_owners')],
        [InlineKeyboardButton("🗑️ Удалить все каналы", callback_data='remove_all')]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    logger.info(f"User {user_id} started the bot.")
    user_logger.info(f"User_{user_id} (@{username}) clicked /start")

    # Initialize user with Папка1 if new user
    data = await storage.load_user_data()
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
        await storage.save_user_data(data)
        logger.info(f"Created Папка1 for new user {user_id}")

    welcome_message = (
        "⭐️ Здравствуйте, я ваш личный доставщик новостей!\n"
        "• Не хватает времени прочитать все telegram каналы?\n"
        "• Устали читать одну и туже новость в разных каналах?\n"
        "• Информационный шум вызывает тревожность?\n\n"
         "💻 Я предлагаю:\n"
        "• Экономить 80% вашего времени\n"
        "• Выделять ключевые моменты новостей\n"
        "• Объединять повторяющаяся посты из каналов\n"
        "• Создавать уникальную ленту новостей\n"
        "• Все это абсолютно бесплатно\n\n"
        "📖 Каналы по одной теме = залог хороших новостей!"
    )

    inline_markup = create_main_menu()
    await _send_reply(update, welcome_message, reply_markup=inline_markup)


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
    await _send_reply(update, help_text)


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
    await _send_reply(update, welcome_message, reply_markup=reply_markup)
