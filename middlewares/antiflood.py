"""
Middleware антифлуда.
Ограничивает количество сообщений от одного пользователя в заданном временном окне.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class AntiFloodMiddleware(BaseMiddleware):
    """
    limit  — максимум сообщений за window секунд.
    window — размер окна в секундах.
    """

    def __init__(self, limit: int = 5, window: int = 10) -> None:
        self.limit = limit
        self.window = window
        # {(user_id, chat_id): [timestamps]}
        self._storage: dict[tuple[int, int], list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.from_user:
            return await handler(event, data)

        key = (event.from_user.id, event.chat.id)
        now = time.monotonic()

        # Убираем старые записи
        self._storage[key] = [t for t in self._storage[key] if now - t < self.window]
        self._storage[key].append(now)

        if len(self._storage[key]) > self.limit:
            logger.info(
                f"Флуд от {event.from_user.id} в чате {event.chat.id}: "
                f"{len(self._storage[key])} сообщений за {self.window}с"
            )
            # Тихо игнорируем — не пропускаем дальше
            return None

        return await handler(event, data)
