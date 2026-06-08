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
# Импортируем все модули хэндлеров
from handlers import moderation, economy, reputation, marriage, misc, profile, roles
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

    # Подключаем роутеры В ПРАВИЛЬНОМ ПОРЯДКЕ
    # Сначала общие и важные команды, чтобы они никогда не перехватывались другими фильтрами
    dp.include_router(misc.router)        # Общие команды (/start, /помощь, настройки) — ТЕПЕРЬ ПЕРВЫЙ!
    dp.include_router(profile.router)     # Профиль и карточки (кто я)
    dp.include_router(reputation.router)  # Репутация и исправленный /топ
    dp.include_router(economy.router)     # Экономика, баланс, казино
    dp.include_router(moderation.router)  # Модерация и правила чата
    dp.include_router(marriage.router)    # Браки и разводы
    dp.include_router(roles.router)       # Должности и ДК

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
