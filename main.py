import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import get_settings
from bot.handlers import admin, balance, quiz, start, top
from bot.handlers.start import setup_bot_commands
from database.session import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
bot = Bot(token=settings.bot_token)
dp = Dispatcher(storage=MemoryStorage())


def register_routers() -> None:
    dp.include_router(start.router)
    dp.include_router(quiz.router)
    dp.include_router(balance.router)
    dp.include_router(top.router)
    dp.include_router(admin.router)


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan")

    await init_db()
    register_routers()
    await setup_bot_commands(bot)

    logger.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
