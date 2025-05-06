import logging
import sys
import asyncio
from telegram_bot import start_bot

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

if __name__ == "__main__":
    asyncio.run(start_bot())
