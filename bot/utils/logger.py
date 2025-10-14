# -*- coding: utf-8 -*-
"""Logging setup for the bot.

Provides two loggers:
- logger: General application logging (bot.log)
- user_logger: User interaction logging (bot_user.log)
"""
import logging
from typing import Tuple

def setup_logging() -> Tuple[logging.Logger, logging.Logger]:
    """Setup and configure logging for the bot.

    Returns:
        Tuple[logging.Logger, logging.Logger]: (logger, user_logger)
            - logger: General application logger
            - user_logger: User interactions logger
    """
    # Configure main logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logger = logging.getLogger(__name__)

    # Create separate logger for user interactions
    user_logger = logging.getLogger('user_interactions')
    user_logger.setLevel(logging.INFO)
    user_handler = logging.FileHandler('bot_user.log', encoding='utf-8')
    user_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    user_logger.addHandler(user_handler)
    # Prevent propagation to root logger to keep it separate
    user_logger.propagate = False

    return logger, user_logger
