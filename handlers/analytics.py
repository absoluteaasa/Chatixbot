"""
ДК 16 — Статистика чата, медленный режим, лог-канал | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import mention_user

router = Router()
CMD = r"^[/!.]?"


def ascii_bar(value: int, max_val: int, width: int = 15) -> str:
    if max_val == 0:
        return "░" * width
    filled = int(value / max_val * width)
    return "█" * filled + "░" * (width - filled)


@router.message(F.text.regexp(CMD + r"статистика(\s|$)", flags=re.IGNORECASE))
async def cmd_stats(message: Message) -> None:
    stats = await repo.get_chat_stats(message.chat.id)
    total = stats["total_messages"]
    users = stats["unique_users"]
    by_day = stats["by_day"]
    lines = [
        "📊 <b>Статистика чата за 7 дней</b>\n",
        f"💬 Сообщений: <b>{total:,}</b>",
        f"👥 Уникальных: <b>{users}</b>\n",
        "<b>По дням:</b>",
    ]
    max_msgs = max((v for _, v in by_day), default=1)
    for date_str, msgs in by_day:
        bar = ascii_bar(msgs, max_msgs, 12)
        lines.append(f"{date_str[-5:]}  [{bar}] {msgs}")
    await message.reply("\n".join(lines))


@router.message(F.text.regexp(CMD + r"медленный(\s|$)", flags=re.IGNORECASE))
async def cmd_slow_mode(message: Message) -> None:
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2:
        cs = await repo.get_chat_settings(message.chat.id)
        sec = cs.slow_mode_seconds if cs else 0
        status = f"{sec} сек." if sec > 0 else "выключен"
        await message.reply(
            f"🐌 <b>Медленный режим:</b> {status}\n\n"
            f"<i>медленный [секунды] — включить\nмедленный 0 — выключить</i>"
        )
        return
    try:
        seconds = int(parts[1])
    except ValueError:
        await message.reply("❌ Укажи количество секунд.")
        return
    await repo.set_slow_mode(message.chat.id, seconds)
    if seconds > 0:
        await message.reply(f"🐌 Медленный режим включён: <b>{seconds} сек.</b> между сообщениями.")
    else:
        await message.reply("✅ Медленный режим выключен.")


@router.message(F.text.regexp(CMD + r"лог(\s|$)", flags=re.IGNORECASE))
async def cmd_set_log(message: Message) -> None:
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2:
        log_id = await repo.get_log_chat(message.chat.id)
        status = f"установлен (id: {log_id})" if log_id else "не установлен"
        await message.reply(
            f"📝 <b>Лог-канал:</b> {status}\n\n"
            f"<i>лог [chat_id] — установить\nлог 0 — отключить</i>"
        )
        return
    try:
        log_chat_id = int(parts[1])
    except ValueError:
        await message.reply("❌ Укажи числовой ID чата.")
        return
    if log_chat_id == 0:
        await repo.set_log_chat(message.chat.id, 0)
        await message.reply("✅ Лог-канал отключён.")
    else:
        await repo.set_log_chat(message.chat.id, log_chat_id)
        await message.reply(f"✅ Лог-канал установлен: <code>{log_chat_id}</code>")
