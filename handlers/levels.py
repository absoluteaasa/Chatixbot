"""
ДК 10 — Уровни, XP, стрики, ачивки, квесты | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from database.repo import LEVEL_NAMES, ACHIEVEMENTS, QUEST_DEFINITIONS, xp_for_level
from utils.helpers import mention_user

router = Router()
CMD = r"^[/!.]?"


def level_bar(xp: int, needed: int, length: int = 10) -> str:
    filled = int(xp / needed * length) if needed else 0
    return "█" * filled + "░" * (length - filled)


@router.message(F.text.regexp(CMD + r"(уровень|lvl|level)(\s|$)", flags=re.IGNORECASE))
async def cmd_level(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    level, xp, needed = await repo.get_level_info(target.id)
    level_name = LEVEL_NAMES.get(min(level, 10), f"Уровень {level}")
    bar = level_bar(xp, needed)
    db_user = await repo.get_user(target.id)
    streak = db_user.streak if db_user else 0
    await message.reply(
        f"📊 <b>Уровень {mention_user(target)}</b>\n\n"
        f"{level_name} — <b>Ур. {level}</b>\n"
        f"XP: {xp}/{needed}\n"
        f"[{bar}]\n\n"
        f"🔥 Стрик: <b>{streak} дн.</b>"
    )


@router.message(F.text.regexp(CMD + r"ачивки(\s|$)", flags=re.IGNORECASE))
async def cmd_achievements(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    earned = await repo.get_achievements(target.id)
    earned_keys = {a.key for a in earned}
    total = len(ACHIEVEMENTS)
    got = len(earned_keys)
    lines = [f"🏆 <b>Ачивки {mention_user(target)}</b> ({got}/{total})\n"]
    for key, data in ACHIEVEMENTS.items():
        icon = "✅" if key in earned_keys else "🔒"
        lines.append(f"{icon} {data['name']} — <i>{data['desc']}</i>")
    await message.reply("\n".join(lines))


@router.message(F.text.regexp(CMD + r"квесты(\s|$)", flags=re.IGNORECASE))
async def cmd_quests(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    quests = await repo.get_today_quests(user.id, message.chat.id)
    lines = ["📋 <b>Ежедневные квесты</b>\n"]
    for q in quests:
        qd = QUEST_DEFINITIONS.get(q.quest_key, {})
        desc = qd.get("desc", q.quest_key)
        if q.completed:
            lines.append(f"✅ {desc} — <i>выполнено! +{q.reward} ирисок</i>")
        else:
            bar = level_bar(q.progress, q.goal, 8)
            lines.append(f"🔹 {desc}\n   [{bar}] {q.progress}/{q.goal} → +{q.reward} 🍬")
    await message.reply("\n".join(lines))
