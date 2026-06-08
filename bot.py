"""
Iris Bot 2.0 — точка входа
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from database.db import init_db
from handlers import moderation, economy, reputation, marriage, misc, profile, roles
from handlers.reputation import router as reputation_router
from middlewares.admin import AdminMiddleware
from middlewares.antiflood import AntiFloodMiddleware

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.FileHandler("iris_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


async def main() -> None:
    logger.info("🌸 Запуск Iris Bot 2.0...")

    # Инициализация БД
    await init_db()
    logger.info("✅ База данных инициализирована")

    # Токен берется из файла конфигурации (из переменных окружения)
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем middleware
    dp.message.middleware(AntiFloodMiddleware(limit=5, window=10))
    dp.message.middleware(AdminMiddleware())

    # Подключаем роутеры
    dp.include_router(profile.router)
    dp.include_router(moderation.router)
    dp.include_router(economy.router)
    dp.include_router(reputation_router)
    dp.include_router(marriage.router)
    dp.include_router(misc.router)
    dp.include_router(roles.router)

    # Удаляем вебхук и запускаем поллинг
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Бот запущен и слушает обновления...")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        logger.info("🛑 Бот остановлен")


if __name__ == "__main__":
    asyncio.run(main())
