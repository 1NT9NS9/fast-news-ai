# -*- coding: utf-8 -*-
"""Admin log statistics handler.

Provides /log command for admins to view weekly user activity statistics.
"""
import os
import logging
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
from telegram import Update
from telegram.ext import ContextTypes

from bot.services import messenger as messenger_service

logger = logging.getLogger(__name__)


async def _send_reply(
    update: Update,
    text: str,
    *,
    reply_markup=None,
    reply: bool = False,
    **kwargs,
) -> None:
    """Send a reply via the messenger wrapper."""
    chat = update.effective_chat
    if chat is None:
        raise RuntimeError("Cannot send message without an active chat.")
    send_kwargs = dict(kwargs)
    if reply_markup is not None:
        send_kwargs["reply_markup"] = reply_markup
    if reply and update.message is not None:
        send_kwargs.setdefault("reply_to_message_id", update.message.message_id)
    await messenger_service.send_text(chat.id, text, **send_kwargs)


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
        await _send_reply(
            update,
            "⚠️ Команда /log не настроена (ADMIN_CHAT_ID_BACKUP не указан в конфигурации)."
        )
        return

    try:
        admin_id = int(admin_chat_id_backup)
    except ValueError:
        await _send_reply(
            update,
            "⚠️ Ошибка конфигурации: ADMIN_CHAT_ID_BACKUP имеет неверный формат."
        )
        return

    if user_id != admin_id:
        await _send_reply(
            update,
            "🚫 У вас нет доступа к этой команде."
        )
        return

    # Parse log file and collect statistics
    try:
        stats = await _parse_log_file()
        queue_metrics = await _gather_queue_metrics()
        system_metrics = await _gather_system_metrics()

        # Format and send response
        message = _format_statistics(stats, queue_metrics, system_metrics)
        await _send_reply(update, message, parse_mode='HTML')

    except FileNotFoundError:
        await _send_reply(
            update,
            "⚠️ Файл bot_user.log не найден."
        )
    except Exception as e:
        await _send_reply(
            update,
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


async def _gather_queue_metrics() -> Optional[Dict[str, Any]]:
    """Fetch rate limiter queue metrics if available."""
    if not messenger_service.is_configured():
        return None
    try:
        return await messenger_service.get_queue_metrics()
    except Exception as exc:  # pylint: disable=broad-except
        logger.debug("Failed to gather queue metrics: %s", exc)
        return None


async def _gather_system_metrics() -> Optional[Dict[str, Any]]:
    """Collect current system resource metrics for the host running the bot."""
    try:
        import psutil  # type: ignore
    except ImportError:
        logger.debug("psutil is not installed; skipping system metrics collection.")
        return None

    try:
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except Exception:  # pylint: disable=broad-except
        cpu_percent = None

    load_avg: Optional[List[float]] = None
    try:
        load_avg_tuple = psutil.getloadavg()  # type: ignore[attr-defined]
        load_avg = [round(value, 2) for value in load_avg_tuple]
    except (AttributeError, OSError):
        load_avg = None

    try:
        virtual_mem = psutil.virtual_memory()
    except Exception:  # pylint: disable=broad-except
        virtual_mem = None

    try:
        swap_mem = psutil.swap_memory()
    except Exception:  # pylint: disable=broad-except
        swap_mem = None

    disk_path = os.getenv("SYSTEM_METRICS_DISK_PATH", os.path.abspath(os.sep))
    try:
        disk_usage = psutil.disk_usage(disk_path)
    except Exception:  # pylint: disable=broad-except
        disk_usage = None

    return {
        "cpu_percent": cpu_percent,
        "load_avg": load_avg,
        "memory": virtual_mem,
        "swap": swap_mem,
        "disk": disk_usage,
        "disk_path": disk_path,
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


def _format_statistics(
    stats: Dict,
    queue_metrics: Optional[Dict[str, Any]] = None,
    system_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """Format statistics into a readable message."""
    unique_users = stats["unique_users"]
    actions = stats["actions"]
    start_date, end_date = stats["date_range"]

    sorted_actions = sorted(actions.items(), key=lambda item: item[1], reverse=True)

    message_lines: List[str] = [
        "<b>Weekly Usage Summary</b>",
        f"Range: {start_date:%Y-%m-%d} - {end_date:%Y-%m-%d}",
        "",
        f"<b>Unique users:</b> {len(unique_users)}",
    ]

    if system_metrics is not None:
        message_lines.append("")
        message_lines.extend(_format_system_metrics(system_metrics))

    if queue_metrics is not None:
        message_lines.append("")
        message_lines.extend(_format_queue_metrics(queue_metrics))

    message_lines.append("")
    message_lines.append("<b>Action counts:</b>")

    if not sorted_actions:
        message_lines.append("<i>No actions recorded.</i>")
    else:
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

        if commands:
            message_lines.append("")
            message_lines.append("<b>Commands</b>")
            for action, count in commands:
                message_lines.append(f"- <code>{action}</code>: {count}")

        if buttons:
            message_lines.append("")
            message_lines.append("<b>Buttons</b>")
            for action, count in buttons:
                message_lines.append(f"- {action}: {count}")

        if other_actions:
            message_lines.append("")
            message_lines.append("<b>Other actions</b>")
            for action, count in other_actions:
                message_lines.append(f"- {action}: {count}")

    total_actions = sum(actions.values())
    message_lines.append("")
    message_lines.append(f"<b>Total actions:</b> {total_actions}")

    return "\n".join(message_lines)


def _format_queue_metrics(metrics: Dict[str, Any]) -> List[str]:
    """Format rate limiter queue metrics for display."""
    queue_depth = int(metrics.get("queue_depth", 0))
    max_delay = float(metrics.get("max_delay_sec", 0.0))
    avg_delay = float(metrics.get("avg_delay_sec", 0.0))
    worst_chat = metrics.get("max_delay_chat_id")
    worst_delay = float(metrics.get("max_delay_chat_sec", 0.0))

    lines = ["<b>Queue Delay Metrics</b>"]
    lines.append(f"- Queue depth: {queue_depth}")
    lines.append(f"- Max delay: {max_delay:.2f}s")
    lines.append(f"- Average delay: {avg_delay:.2f}s")

    if queue_depth == 0 or worst_chat is None:
        lines.append("- Highest per-chat delay: 0.00s")
    else:
        lines.append(f"- Highest per-chat delay: {worst_delay:.2f}s (chat {worst_chat})")

    return lines


def _format_system_metrics(metrics: Dict[str, Any]) -> List[str]:
    """Format host system metrics for display in /log output."""
    lines: List[str] = ["<b>Server Metrics</b>"]

    cpu_percent = metrics.get("cpu_percent")
    if cpu_percent is not None:
        lines.append(f"- CPU usage: {cpu_percent:.1f}%")
    else:
        lines.append("- CPU usage: unavailable")

    load_avg = metrics.get("load_avg")
    if load_avg:
        formatted = "/".join(f"{value:.2f}" for value in load_avg)
        lines.append(f"- Load avg (1m/5m/15m): {formatted}")

    memory = metrics.get("memory")
    if memory is not None:
        lines.append(
            "- RAM used: "
            f"{_human_bytes(memory.used)} / {_human_bytes(memory.total)} "
            f"({memory.percent:.1f}%)"
        )
    else:
        lines.append("- RAM used: unavailable")

    swap = metrics.get("swap")
    if swap is not None and getattr(swap, "total", 0) > 0:
        lines.append(
            "- Swap used: "
            f"{_human_bytes(swap.used)} / {_human_bytes(swap.total)} "
            f"({swap.percent:.1f}%)"
        )

    disk = metrics.get("disk")
    disk_path = metrics.get("disk_path", os.path.abspath(os.sep))
    if disk is not None:
        lines.append(
            f"- Disk ({disk_path}): "
            f"{_human_bytes(disk.used)} / {_human_bytes(disk.total)} "
            f"({disk.percent:.1f}%)"
        )
    else:
        lines.append(f"- Disk ({disk_path}): unavailable")

    return lines


def _human_bytes(num_bytes: float) -> str:
    """Convert byte counts to a short, human-readable string."""
    step = 1024.0
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    value = float(num_bytes)
    for unit in units:
        if value < step:
            return f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} PiB"
