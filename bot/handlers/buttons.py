# -*- coding: utf-8 -*-
"""Button callback handlers and channel owner forms."""

from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils.config import ADMIN_CHAT_ID, MAX_SUMMARY_POSTS_LIMIT, MAX_NEWS_TIME_LIMIT_HOURS
from bot.utils.logger import setup_logging
from bot.services import StorageService, ScraperService

# Setup logging
logger, user_logger = setup_logging()

# Import conversation states
from bot.handlers.manage import (
    WAITING_FOR_CHANNEL_ADD,
    WAITING_FOR_CHANNEL_REMOVE,
    WAITING_FOR_TIME_INTERVAL,
    WAITING_FOR_NEWS_COUNT,
    WAITING_FOR_NEW_FOLDER_NAME,
    format_time_display,
    send_channel_list,
    create_folder_management_menu
)

# Channel owner form states
WAITING_FOR_ADD_TO_FEED_CHANNEL = 5
WAITING_FOR_ADD_TO_FEED_HASHTAG = 6
WAITING_FOR_ADD_TO_FEED_DESCRIPTION = 7
WAITING_FOR_REMOVE_FROM_FEED_CHANNEL = 8
WAITING_FOR_REMOVE_FROM_FEED_REASON = 9
WAITING_FOR_RESTRICT_ACCESS_CHANNEL = 10
WAITING_FOR_RESTRICT_ACCESS_REASON = 11


def create_main_menu():
    """Create the main menu keyboard with folder management."""
    keyboard = [
        [InlineKeyboardButton("✨ Начать", callback_data='start_plans')],
        [InlineKeyboardButton("📰 Получить новости", callback_data='get_news')],
        [InlineKeyboardButton("📁 Управление папками", callback_data='manage_folders')],
        [InlineKeyboardButton("➕ Добавить канал", callback_data='add_channel'), InlineKeyboardButton("➖ Удалить канал", callback_data='remove_channel')],
        [InlineKeyboardButton("📋 Список каналов", callback_data='list_channels')],
        [InlineKeyboardButton("⏰ Временной диапазон", callback_data='time_interval'), InlineKeyboardButton("📊 Количество новостей", callback_data='news_count')],
        [InlineKeyboardButton("🔥Лента новостей", callback_data='news_feed')],
        [InlineKeyboardButton("⭐️ Для владельцев каналов", callback_data='for_channel_owners')],
        [InlineKeyboardButton("🗑️ Удалить все каналы", callback_data='remove_all')]
    ]
    return InlineKeyboardMarkup(keyboard)


def create_return_menu_button():
    """Create keyboard with only return to menu button."""
    keyboard = [
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


def create_plans_menu():
    """Create keyboard for subscription plans."""
    keyboard = [
        [InlineKeyboardButton("Подключить Plus (1000 руб/месяц)", callback_data='connect_plus')],
        [InlineKeyboardButton("Подключить Pro (2000 руб/месяц)", callback_data='connect_pro')],
        [InlineKeyboardButton("Подключить Enterprise", callback_data='connect_enterprise')],
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


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks."""
    storage = StorageService()
    scraper = ScraperService()

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

    elif query.data == 'start_plans':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Start' button")
        reply_markup = create_plans_menu()

        plans_message = (
            "Нажмите в главном меню <📰 Получить новости>\n\n" 
            "Ваш тариф: Free\n\n"
            "Тарифы:\n"
            "• Free: 10 каналов | 2 папки | 3 /news в день | время 1ч-7д\n"
            "• Plus: 25 каналов | 3 папки | 4 /news в день | время 1ч-1м\n"
            "• Pro:  50 каналов | 5 папок | 5 /news в день | время 1ч-2м\n"
            "• Enterprise: Хотите увеличить временной интервал или другие параметры, напишите @fast_news_ai_admin"
        )

        await query.message.reply_text(plans_message, reply_markup=reply_markup)
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
        current_time = await storage.get_user_time_limit(user_id)

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
        current_max = await storage.get_user_max_posts(user_id)
        await query.message.reply_text(
            f"📊 Текущее количество новостей: {current_max}\n\n"
            f"Чтобы изменить, введите количество (например: 10)\n"
            f"Максимум: {MAX_SUMMARY_POSTS_LIMIT} новостей"
        )
        return WAITING_FOR_NEWS_COUNT

    elif query.data == 'get_news':
        from bot.handlers.news import news_command_internal
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
        message_text = 'Здесь будут каналы по темам "скоро" ... '
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

        channels = await storage.get_user_channels(user_id)
        reply_markup = create_return_menu_button()

        if not channels:
            await processing_msg.edit_text(
                "📭 У вас нет добавленных каналов.",
                reply_markup=reply_markup
            )
        else:
            channel_count = len(channels)
            await storage.set_user_channels(user_id, [])
            await processing_msg.edit_text(
                f"🗑️ Все каналы ({channel_count}) были удалены.",
                reply_markup=reply_markup
            )
        return ConversationHandler.END

    elif query.data in ['connect_plus', 'connect_pro', 'connect_enterprise']:
        plan_name = query.data.replace('connect_', '').capitalize()
        user_logger.info(f"User_{user_id} (@{username}) clicked '{plan_name}' plan button")

        # Save subscription request to JSON
        await storage.save_plan_subscription(user_id, username, plan_name)

        reply_markup = create_return_menu_button()
        await query.message.reply_text(
            "Спасибо за ваш выбор! Сейчас мы добавляем способ оплаты\n"
            "Когда появиться возможность оплатить, мы отправим Вам сообщение",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    elif query.data == 'manage_folders':
        user_logger.info(f"User_{user_id} (@{username}) clicked 'Manage Folders' button")
        # Send immediate feedback
        processing_msg = await query.message.reply_text("⏳ Загружаю папки...")

        active_folder = await storage.get_active_folder_name(user_id)
        folders = await storage.get_user_folders(user_id)
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

        if await storage.switch_active_folder(user_id, folder_name):
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
        folders = await storage.get_user_folders(user_id)

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

        if await storage.delete_folder(user_id, folder_name):
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


# ============================================================================
# Channel Owner Form Handlers
# ============================================================================

async def handle_add_to_feed_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for add to feed form."""
    scraper = ScraperService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Normalize channel name: remove multiple @ symbols
    while channel.startswith('@@'):
        channel = channel[1:]

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_ADD_TO_FEED_CHANNEL

    # Validate channel accessibility (same as main Add Channel feature)
    is_valid, error_msg = await scraper.validate_channel_access(channel, update)

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


async def handle_remove_from_feed_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for remove from feed form."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Normalize channel name: remove multiple @ symbols
    while channel.startswith('@@'):
        channel = channel[1:]

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_REMOVE_FROM_FEED_CHANNEL

    # Check if channel is in feed
    if not await storage.check_channel_in_feed(channel):
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


async def handle_restrict_access_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle channel name input for restrict access form."""
    scraper = ScraperService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Normalize channel name: remove multiple @ symbols
    while channel.startswith('@@'):
        channel = channel[1:]

    # Validate channel format
    if not channel.startswith('@'):
        await update.message.reply_text(
            "❌ Название канала должно начинаться с @\n"
            "Попробуйте еще раз:"
        )
        return WAITING_FOR_RESTRICT_ACCESS_CHANNEL

    # Validate channel accessibility (same as main Add Channel feature)
    is_valid, error_msg = await scraper.validate_channel_access(channel, update)

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
