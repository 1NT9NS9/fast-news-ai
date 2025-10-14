# -*- coding: utf-8 -*-
"""Channel and folder management handlers."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from bot.utils.config import MAX_CHANNELS, MAX_NEWS_TIME_LIMIT_HOURS, MAX_SUMMARY_POSTS_LIMIT
from bot.utils.logger import setup_logging
from bot.services import StorageService, ScraperService

# Setup logging
logger, user_logger = setup_logging()

# Conversation states
WAITING_FOR_CHANNEL_ADD = 1
WAITING_FOR_CHANNEL_REMOVE = 2
WAITING_FOR_TIME_INTERVAL = 3
WAITING_FOR_NEWS_COUNT = 4
WAITING_FOR_NEW_FOLDER_NAME = 12


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


async def create_folder_management_menu(user_id):
    """Create folder management menu with all folders."""
    storage = StorageService()
    # Load user data once instead of calling get_user_folders and get_active_folder_name separately
    data = await storage.load_user_data()
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
    storage = StorageService()
    data = await storage.load_user_data()
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
        all_channels = await storage.get_all_user_channels(user_id)

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


# ============================================================================
# Command Handlers
# ============================================================================

async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /add command."""
    storage = StorageService()
    scraper = ScraperService()

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
    channels = await storage.get_user_channels(user_id)
    # Get all channels across all folders
    all_channels = await storage.get_all_user_channels(user_id)

    # Check if channel already exists in ANY folder (no duplicates allowed)
    if channel in all_channels:
        await update.message.reply_text(f"ℹ️ {channel} уже добавлен в одну из Ваших папок.")
        return

    # Check channel limit (global across all folders)
    if len(all_channels) >= MAX_CHANNELS:
        await update.message.reply_text(f"❌ Вы достигли максимального лимита в {MAX_CHANNELS} каналов.")
        return

    # Validate channel accessibility
    is_valid, error_msg = await scraper.validate_channel_access(channel, update)

    if not is_valid:
        logger.warning(f"User {user_id} tried to add inaccessible channel {channel}: {error_msg}")
        return

    # Add channel
    channels.append(channel)
    await storage.set_user_channels(user_id, channels)

    logger.info(f"User {user_id} added channel {channel}.")
    user_logger.info(f"User_{user_id} (@{username}) specified /add {channel}")
    await update.message.reply_text(f"✅ {channel} был добавлен.")


async def remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove command."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if channel name is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /remove (no channel specified)")
        await update.message.reply_text("❌ Укажите название канала. Например: /remove @channelname")
        return

    channel = context.args[0]

    # Get current user channels
    channels = await storage.get_user_channels(user_id)

    # Check if channel exists in user's list
    if channel not in channels:
        await update.message.reply_text(f"❌ {channel} не найден в вашем списке.")
        return

    # Remove channel
    channels.remove(channel)
    await storage.set_user_channels(user_id, channels)

    user_logger.info(f"User_{user_id} (@{username}) specified /remove {channel}")
    await update.message.reply_text(f"🗑️ {channel} был удален.")


async def remove_all_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /remove_all command."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked /remove_all")

    # Get current user channels
    channels = await storage.get_user_channels(user_id)

    if not channels:
        await update.message.reply_text("📭 У вас нет добавленных каналов.")
        return

    # Remove all channels
    channel_count = len(channels)
    await storage.set_user_channels(user_id, [])

    await update.message.reply_text(f"🗑️ Все каналы ({channel_count}) были удалены.")


async def list_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /list command - show all folders and channels."""
    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    user_logger.info(f"User_{user_id} (@{username}) clicked /list")

    await send_channel_list(update, user_id)


async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /time command - set news time range."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if hours value is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /time (view current)")
        current_time = await storage.get_user_time_limit(user_id)

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
        await storage.set_user_time_limit(user_id, hours)
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
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"

    # Check if posts value is provided
    if not context.args:
        user_logger.info(f"User_{user_id} (@{username}) clicked /posts (view current)")
        current_max = await storage.get_user_max_posts(user_id)
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
        await storage.set_user_max_posts(user_id, max_posts)
        logger.info(f"User {user_id} set max posts to {max_posts}.")
        user_logger.info(f"User_{user_id} (@{username}) specified /posts {max_posts}")

        await update.message.reply_text(
            f"✅ Количество новостей установлено: {max_posts}\n"
            f"Команда /news будет показывать до {max_posts} новостей."
        )

    except ValueError:
        await update.message.reply_text("❌ Укажите корректное число. Например: /posts 10")


async def restore_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /restore_backup admin command."""
    from bot.utils.config import ADMIN_CHAT_ID, ADMIN_CHAT_ID_INT
    from datetime import datetime

    storage = StorageService()

    user = update.effective_user
    admin_id = ADMIN_CHAT_ID_INT

    if admin_id is None:
        await update.message.reply_text('ADMIN_CHAT_ID is not configured. Set it in the environment to enable restores.')
        return

    if user.id != admin_id:
        await update.message.reply_text('You are not authorized to use this command.')
        return

    backups = storage.list_user_data_backups()

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
        await storage.restore_user_data_from_backup(selected['path'])
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


# ============================================================================
# Conversation Input Handlers
# ============================================================================

async def handle_add_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for adding a channel."""
    storage = StorageService()
    scraper = ScraperService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Validate channel format (should start with @)
    if not channel.startswith('@'):
        await update.message.reply_text("❌ Название канала должно начинаться с @")
        return WAITING_FOR_CHANNEL_ADD

    # Get current user channels (from active folder)
    channels = await storage.get_user_channels(user_id)
    # Get all channels across all folders
    all_channels = await storage.get_all_user_channels(user_id)

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
        from bot.handlers.start import create_main_menu
        reply_markup = create_main_menu()
        await update.message.reply_text(
            f"❌ Вы достигли максимального лимита в {MAX_CHANNELS} каналов.",
            reply_markup=reply_markup
        )
        return ConversationHandler.END

    # Validate channel accessibility
    is_valid, error_msg = await scraper.validate_channel_access(channel, update)

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
    await storage.set_user_channels(user_id, channels)

    logger.info(f"User {user_id} added channel {channel}.")
    user_logger.info(f"User_{user_id} (@{username}) added channel {channel} via button")

    await update.message.reply_text(
        "Выберите действие:",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def handle_remove_channel_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for removing a channel."""
    storage = StorageService()

    user_id = update.effective_user.id
    username = update.effective_user.username or "unknown"
    channel = update.message.text.strip()

    # Get current user channels
    channels = await storage.get_user_channels(user_id)

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
    await storage.set_user_channels(user_id, channels)

    user_logger.info(f"User_{user_id} (@{username}) removed channel {channel} via button")
    reply_markup = create_remove_another_menu()
    await update.message.reply_text(
        f"🗑️ {channel} был удален.",
        reply_markup=reply_markup
    )

    return ConversationHandler.END


async def handle_time_interval_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user input for setting time interval."""
    storage = StorageService()

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
        await storage.set_user_time_limit(user_id, hours)
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
    storage = StorageService()

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
        await storage.set_user_max_posts(user_id, max_posts)
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
    storage = StorageService()

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
    if await storage.create_folder(user_id, folder_name):
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
