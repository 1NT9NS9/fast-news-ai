# -*- coding: utf-8 -*-
"""
Backward compatibility entry point.

This file maintains compatibility for users running `python bot.py`.
The actual bot logic has been moved to the modular structure in bot/main.py.
"""

if __name__ == '__main__':
    from bot.main import main
    main()
