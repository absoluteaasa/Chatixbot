"""
Middleware для проверки прав администратора.
Помечает сообщение флагом is_admin, который используется хэндлерами модерации.
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    """
    Добавляет в data["is_admin"] = True/False.
    Не блокирует запрос — хэндлеры сами проверяют флаг.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        data["is_admin"] = False

        if not isinstance(event, Message):
            return await handler(event, data)

        chat = event.chat
        user = event.from_user

        # В личных чатах — всегда "админ"
        if chat.type == "private":
            data["is_admin"] = True
            return await handler(event, data)

        if user:
            try:
                member = await event.bot.get_chat_member(chat.id, user.id)
                data["is_admin"] = member.status in ("administrator", "creator")
            except Exception as e:
                logger.warning(f"Не удалось получить статус участника {user.id}: {e}")

        return await handler(event, data)
