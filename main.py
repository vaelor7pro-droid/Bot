"""Botni ishga tushirish nuqtasi. Railway'da: python main.py"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import handlers
from config import settings
from models import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. Railway'da Variables bo'limiga BOT_TOKEN qo'shing "
            "(qiymatini @BotFather'dan oling)."
        )

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(handlers.router)

    logger.info("Ma'lumotlar bazasi tayyorlanmoqda...")
    await init_db()

    await handlers.setup_bot_commands(bot)

    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
