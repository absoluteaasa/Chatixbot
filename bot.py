"""Chatix b1.6 | Чат-менеджер"""
import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from config import settings
from database.db import init_db
from handlers import moderation, economy, reputation, marriage, misc, profile, roles, shop, spam, top, banlist
from middlewares.admin import AdminMiddleware
from middlewares.antiflood import AntiFloodMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("chatix.log", encoding="utf-8"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


async def main():
    logger.info("🤖 Запуск Chatix b1.6...")
    await init_db()
    logger.info("✅ БД готова")
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.message.middleware(AntiFloodMiddleware(limit=5, window=10))
    dp.message.middleware(AdminMiddleware())

    # Важно: misc первым — там обработчик new_member и платежей
    dp.include_router(misc.router)
    dp.include_router(roles.router)
    dp.include_router(banlist.router)
    dp.include_router(shop.router)
    dp.include_router(spam.router)
    dp.include_router(top.router)
    dp.include_router(economy.router)
    dp.include_router(reputation.router)
    dp.include_router(marriage.router)
    dp.include_router(profile.router)
    dp.include_router(moderation.router)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("🚀 Chatix b1.6 запущен!")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
