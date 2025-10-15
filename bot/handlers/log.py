# -*- coding: utf-8 -*-
"""Admin log statistics handler.

Provides /log command for admins to view weekly user activity statistics.
"""
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Set
from telegram import Update
from telegram.ext import ContextTypes


async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /log command - show weekly statistics from bot_user.log.

    Only accessible to users with ADMIN_CHAT_ID_BACKUP.

    Statistics include:
    - Unique users (count of distinct user IDs)
    - Total clicks for each button/action type

    Args:
        update: Telegram update object
        context: Telegram context object
    """
    user_id = update.effective_user.id

    # Access control - only ADMIN_CHAT_ID_BACKUP can use this command
    admin_chat_id_backup = os.getenv('ADMIN_CHAT_ID_BACKUP')

    if not admin_chat_id_backup:
        await update.message.reply_text(
            "⚠️ Команда /log не настроена (ADMIN_CHAT_ID_BACKUP не указан в конфигурации)."
        )
        return

    try:
        admin_id = int(admin_chat_id_backup)
    except ValueError:
        await update.message.reply_text(
            "⚠️ Ошибка конфигурации: ADMIN_CHAT_ID_BACKUP имеет неверный формат."
        )
        return

    if user_id != admin_id:
        await update.message.reply_text(
            "🚫 У вас нет доступа к этой команде."
        )
        return

    # Parse log file and collect statistics
    try:
        stats = await _parse_log_file()

        # Format and send response
        message = _format_statistics(stats)
        await update.message.reply_text(message, parse_mode='HTML')

    except FileNotFoundError:
        await update.message.reply_text(
            "⚠️ Файл bot_user.log не найден."
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка при анализе логов: {str(e)}"
        )


async def _parse_log_file() -> Dict:
    """Parse bot_user.log and extract statistics for the last 7 days.

    Returns:
        Dict with keys:
            - unique_users: Set of user IDs
            - actions: Dict mapping action name to count
            - date_range: Tuple of (start_date, end_date)
    """
    log_file_path = 'bot_user.log'

    if not os.path.exists(log_file_path):
        raise FileNotFoundError(f"Log file not found: {log_file_path}")

    # Calculate date range (last 7 days)
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    unique_users: Set[int] = set()
    actions: Dict[str, int] = defaultdict(int)

    with open(log_file_path, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                # Parse log line format: "YYYY-MM-DD HH:MM:SS,mmm - User_ID (@username) action"
                if ' - User_' not in line:
                    continue

                # Extract timestamp
                timestamp_str = line.split(',')[0]
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

                # Skip if outside date range
                if timestamp < week_ago:
                    continue

                # Extract user ID
                user_part = line.split('User_')[1].split(' ')[0]
                user_id = int(user_part)
                unique_users.add(user_id)

                # Extract action (everything after "@username) ")
                action_part = line.split(') ', 1)[1].strip()

                # Normalize action text
                action = _normalize_action(action_part)
                actions[action] += 1

            except (ValueError, IndexError):
                # Skip malformed lines
                continue

    return {
        'unique_users': unique_users,
        'actions': actions,
        'date_range': (week_ago, now)
    }


def _normalize_action(action_text: str) -> str:
    """Normalize action text for grouping similar actions.

    Examples:
        "clicked /start" -> "/start"
        "clicked 'Add channel' button" -> "Add channel"
        "added channel @example via button" -> "added channel"
        "set time to 24 via button" -> "set time"

    Args:
        action_text: Raw action text from log

    Returns:
        Normalized action name
    """
    action = action_text

    # Remove "clicked" prefix
    if action.startswith('clicked '):
        action = action[8:]

    # Handle button clicks
    if action.startswith("'") and "' button" in action:
        # Extract text between quotes: 'Add channel' button -> Add channel
        action = action.split("'")[1]

    # Handle persistent button clicks
    if action.startswith("persistent '") and "' button" in action:
        action = action.split("'")[1]

    # Normalize complex actions to categories
    if action.startswith('added channel '):
        action = 'added channel'
    elif action.startswith('removed channel '):
        action = 'removed channel'
    elif action.startswith('switching to folder '):
        action = 'switched folder'
    elif action.startswith('set time to '):
        action = 'set time'
    elif action.startswith('set max posts to '):
        action = 'set max posts'
    elif action.startswith('created folder '):
        action = 'created folder'
    elif action.startswith('deleted folder '):
        action = 'deleted folder'
    elif action.startswith('renamed folder '):
        action = 'renamed folder'
    elif 'specified /time' in action:
        action = '/time (specified)'
    elif 'exported backup' in action:
        action = 'exported backup'
    elif 'imported backup' in action:
        action = 'imported backup'

    return action


def _format_statistics(stats: Dict) -> str:
    """Format statistics into a readable message.

    Args:
        stats: Statistics dict from _parse_log_file

    Returns:
        Formatted HTML message
    """
    unique_users = stats['unique_users']
    actions = stats['actions']
    start_date, end_date = stats['date_range']

    # Sort actions by count (descending)
    sorted_actions = sorted(actions.items(), key=lambda x: x[1], reverse=True)

    # Build message
    message = f"📊 <b>Статистика за неделю</b>\n"
    message += f"📅 {start_date.strftime('%Y-%m-%d')} — {end_date.strftime('%Y-%m-%d')}\n\n"

    message += f"👥 <b>Уникальных пользователей:</b> {len(unique_users)}\n\n"

    message += f"🔘 <b>Действия пользователей:</b>\n"

    if not sorted_actions:
        message += "<i>Нет данных</i>\n"
    else:
        # Group actions by category for better readability
        commands = []
        buttons = []
        other_actions = []

        for action, count in sorted_actions:
            if action.startswith('/'):
                commands.append((action, count))
            elif action.startswith(('added', 'removed', 'created', 'deleted', 'renamed', 'switched', 'set ', 'exported', 'imported', 'entered')):
                other_actions.append((action, count))
            else:
                buttons.append((action, count))

        # Display commands
        if commands:
            message += "\n<b>Команды:</b>\n"
            for action, count in commands:
                message += f"  • <code>{action}</code>: {count}\n"

        # Display buttons
        if buttons:
            message += "\n<b>Кнопки:</b>\n"
            for action, count in buttons:
                message += f"  • {action}: {count}\n"

        # Display other actions
        if other_actions:
            message += "\n<b>Другие действия:</b>\n"
            for action, count in other_actions:
                message += f"  • {action}: {count}\n"

    # Total actions
    total_actions = sum(actions.values())
    message += f"\n<b>Всего действий:</b> {total_actions}"

    return message
