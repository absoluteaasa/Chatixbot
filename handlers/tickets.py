"""
ДК 15 — Тикеты и жалобы | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import mention_user

router = Router()
CMD = r"^[/!.]?"


@router.message(F.text.regexp(CMD + r"жалоба(\s|$)", flags=re.IGNORECASE))
async def cmd_report(message: Message) -> None:
    user = message.from_user
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("ℹ️ Ответь на сообщение нарушителя: <code>жалоба [причина]</code>")
        return
    target = message.reply_to_message.from_user
    if target.id == user.id:
        await message.reply("🤨 Нельзя жаловаться на самого себя.")
        return
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split(maxsplit=1)
    reason = parts[1] if len(parts) > 1 else "Без причины"
    msg_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    ticket = await repo.create_ticket(
        message.chat.id, user.id, target.id, msg_text[:500], reason
    )
    # Уведомляем в лог-чат если настроен
    log_chat_id = await repo.get_log_chat(message.chat.id)
    if log_chat_id:
        try:
            target_name = target.full_name or target.username or str(target.id)
            reporter_name = user.full_name or user.username or str(user.id)
            await message.bot.send_message(
                log_chat_id,
                f"🚨 <b>Тикет #{ticket.id}</b>\n\n"
                f"👤 Нарушитель: {target_name} (id: {target.id})\n"
                f"📝 Жалобщик: {reporter_name}\n"
                f"💬 Причина: {reason}\n"
                f"📄 Сообщение: {msg_text[:200] or 'нет текста'}"
            )
        except Exception:
            pass
    await message.reply(
        f"✅ Жалоба #{ticket.id} подана!\n"
        f"Администраторы рассмотрят в ближайшее время."
    )


@router.message(F.text.regexp(CMD + r"тикеты(\s|$)", flags=re.IGNORECASE))
async def cmd_tickets(message: Message) -> None:
    tickets = await repo.get_open_tickets(message.chat.id)
    if not tickets:
        await message.reply("📭 Открытых тикетов нет.")
        return
    lines = [f"📋 <b>Открытые тикеты</b> ({len(tickets)})\n"]
    for t in tickets:
        target = await repo.get_user(t.target_id)
        target_name = (target.full_name or target.username or str(t.target_id)) if target else str(t.target_id)
        lines.append(
            f"[#{t.id}] {target_name}\n"
            f"  Причина: {t.reason[:60]}\n"
            f"  <code>закрыть_тикет {t.id}</code>"
        )
    await message.reply("\n\n".join(lines) if len(lines) > 1 else lines[0])


@router.message(F.text.regexp(CMD + r"закрыть_тикет(\s|$)", flags=re.IGNORECASE))
async def cmd_resolve_ticket(message: Message) -> None:
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: <code>закрыть_тикет [ID]</code>")
        return
    ok = await repo.resolve_ticket(int(parts[1]))
    if ok:
        await message.reply(f"✅ Тикет #{parts[1]} закрыт.")
    else:
        await message.reply("❌ Тикет не найден.")
