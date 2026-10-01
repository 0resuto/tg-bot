"""
Entry point for the Telegram bot application.
"""

from __future__ import annotations

import asyncio

from bot.app import main

if __name__ == "__main__":
    asyncio.run(main())
