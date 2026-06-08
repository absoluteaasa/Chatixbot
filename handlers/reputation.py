"""
Модуль репутации и статистики:
  + / - в ответ на сообщение — изменение кармы
  /топ — топ богачей, активных, репутации
  /профиль — статистика пользователя
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from database import repo
from utils.helpers import format_balance, mention_user

logger = logging.getLogger(__name__)
router = Router()


# ─── Голосование репутации ────────────────────────────────────────────────────

@router.message(F.reply_to_message & F.text.regexp(r"^\s*[+\-]\s*$"))
async def cmd_reputation_vote(message: Message) -> None:
    """
    Если пользователь отвечает на сообщение и пишет '+' или '-' — меняет репутацию.
    """
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return

    voter = message.from_user
    target = message.reply_to_message.from_user
    text = (message.text or "").strip()

    if voter.id == target.id:
        await message.reply("🙄 Нельзя голосовать за самого себя!")
        return

    if target.is_bot:
        await message.reply("🤖 Ботам репутация не нужна.")
        return

    value = 1 if text == "+" else -1

    try:
        await repo.get_or_create_user(voter.id, voter.username, voter.full_name)
        await repo.get_or_create_user(target.id, target.username, target.full_name)

        success, msg = await repo.change_reputation(voter.id, target.id, message.chat.id, value)
        if success:
            action = "повысил(а)" if value > 0 else "понизил(а)"
            await message.reply(f"⭐ {mention_user(voter)} {action} репутацию {mention_user(target)}!")
        else:
            await message.reply(f"⚠️ {msg}")
    except Exception as e:
        logger.error(f"Ошибка в cmd_reputation_vote: {e}")


# ─── /топ ─────────────────────────────────────────────────────────────────────

@router.message(Command("топ"))
async def cmd_top(message: Message) -> None:
    try:
        top = await repo.get_top_users(limit=10)
        
        sections = []

        # Топ богачей
        rich_lines = ["🏆 <b>Топ богачей</b>"]
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
        if top and "rich" in top and top["rich"]:
            for i, u in enumerate(top["rich"]):
                if i >= len(medals): break
                rich_lines.append(f"{medals[i]} {u.full_name or u.username or u.id} — {format_balance(u.balance)}")
        else:
            rich_lines.append("Список пуст")
        sections.append("\n".join(rich_lines))

        # Топ активных
        active_lines = ["💬 <b>Топ активных</b>"]
        if top and "active" in top and top["active"]:
            for i, u in enumerate(top["active"]):
                if i >= len(medals): break
                active_lines.append(f"{medals[i]} {u.full_name or u.username or u.id} — {u.messages_count} соб.")
        else:
            active_lines.append("Список пуст")
        sections.append("\n".join(active_lines))

        await message.reply("\n\n".join(sections))
        
    except Exception as e:
        logger.error(f"Ошибка в команде /топ: {e}")
        await message.reply("⚠️ Ошибка при генерации топа пользователей. Проверьте базу данных.")
