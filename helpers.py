"""
Вспомогательные функции, используемые в нескольких модулях.
"""

from __future__ import annotations

import re
from datetime import timedelta

from aiogram.types import Message, User


def mention_user(user: User) -> str:
    """Возвращает HTML-упоминание пользователя."""
    name = user.full_name or user.username or str(user.id)
    return f'<a href="tg://user?id={user.id}">{name}</a>'


def parse_duration(text: str) -> timedelta | None:
    """
    Парсит строку вида '10m', '2h', '1d' в timedelta.
    Возвращает None при неверном формате.
    """
    match = re.fullmatch(r"(\d+)([mhd])", text.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    return {"m": timedelta(minutes=value), "h": timedelta(hours=value), "d": timedelta(days=value)}.get(unit)


def plural_ru(n: int, one: str, few: str, many: str) -> str:
    """Склонение числительных: plural_ru(5, 'ириска', 'ириски', 'ирисок')"""
    if 11 <= (n % 100) <= 19:
        return many
    r = n % 10
    if r == 1:
        return one
    if 2 <= r <= 4:
        return few
    return many


def format_balance(amount: int) -> str:
    word = plural_ru(amount, "ириска", "ириски", "ирисок")
    return f"🍬 {amount:,} {word}".replace(",", " ")


def extract_target(message: Message) -> User | None:
    """
    Извлекает цель команды:
    1) Из reply (ответ на сообщение)
    2) Из упоминания в тексте
    """
    if message.reply_to_message and message.reply_to_message.from_user:
        return message.reply_to_message.from_user
    return None


def contains_link(text: str) -> bool:
    """Проверяет, содержит ли текст URL."""
    url_pattern = re.compile(
        r"(https?://|www\.|t\.me/|tg://)", re.IGNORECASE
    )
    return bool(url_pattern.search(text))
