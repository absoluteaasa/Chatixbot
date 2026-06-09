"""
Управление чатом Chatix b1.7:
смена названия/описания, закреп, очистка сообщений,
кик неактивных, дуэли, заметки
"""
from __future__ import annotations
import asyncio, logging, re
from datetime import datetime, timedelta
from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from database import repo
from utils.helpers import mention_user, extract_target

logger = logging.getLogger(__name__)
router = Router()

CMD = r"^[/!.]?"

def admin_only(handler):
    async def wrapper(message: Message, is_admin: bool = False, **kwargs):
        if not is_admin:
            await message.reply("⛔ Только для администраторов!")
            return
        return await handler(message, is_admin=is_admin, **kwargs)
    return wrapper


# ─── Смена названия чата ──────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+название\s+.+", flags=2))
@admin_only
async def cmd_set_title(message: Message, **_):
    title = (message.text or "").split(None, 1)[1].strip() if len((message.text or "").split(None, 1)) > 1 else ""
    # убираем "+название" из начала
    raw = (message.text or "")
    title = re.sub(r"^\+название\s*", "", raw, flags=re.IGNORECASE).strip()
    if not title:
        await message.reply("ℹ️ Пример: <code>+название Мой чат</code>")
        return
    try:
        await message.bot.set_chat_title(message.chat.id, title)
        await message.reply(f"✅ Название чата изменено на: <b>{title}</b>")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Смена описания чата ──────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+описание_чата\s*", flags=2))
@admin_only
async def cmd_set_description(message: Message, **_):
    desc = re.sub(r"^\+описание_чата\s*", "", (message.text or ""), flags=re.IGNORECASE).strip()
    try:
        await message.bot.set_chat_description(message.chat.id, desc or "")
        await message.reply(f"✅ Описание чата обновлено!")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Закреп сообщения ─────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"закреп$", flags=2))
@admin_only
async def cmd_pin(message: Message, **_):
    if not message.reply_to_message:
        await message.reply("ℹ️ Ответь на сообщение которое нужно закрепить.")
        return
    try:
        await message.bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id)
        await message.reply("📌 Сообщение закреплено!")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(F.text.regexp(CMD + r"открепить$", flags=2))
@admin_only
async def cmd_unpin(message: Message, **_):
    try:
        if message.reply_to_message:
            await message.bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id)
        else:
            await message.bot.unpin_all_chat_messages(message.chat.id)
        await message.reply("📌 Сообщение(я) откреплено!")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Очистка сообщений ────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"очистить(\s+\d+)?$", flags=2))
@admin_only
async def cmd_clear(message: Message, **_):
    text = (message.text or "").strip()
    match = re.search(r"(\d+)$", text)
    count = int(match.group(1)) if match else 10
    count = min(count, 100)  # максимум 100

    deleted = 0
    msg_id = message.message_id
    errors = 0
    for i in range(count):
        try:
            await message.bot.delete_message(message.chat.id, msg_id - i - 1)
            deleted += 1
        except Exception:
            errors += 1
            if errors > 5:
                break

    try:
        await message.delete()
    except Exception:
        pass

    info = await message.answer(f"🧹 Удалено сообщений: <b>{deleted}</b>")
    await asyncio.sleep(3)
    try:
        await info.delete()
    except Exception:
        pass


# ─── Кик неактивных ───────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"кик\s+неактив(\s+\d+)?$", flags=2))
@admin_only
async def cmd_kick_inactive(message: Message, **_):
    text = (message.text or "").strip()
    match = re.search(r"(\d+)$", text)
    days = int(match.group(1)) if match else 30
    cutoff = datetime.utcnow() - timedelta(days=days)

    await message.reply(f"🔍 Ищу неактивных (не писали {days}+ дней)...")

    try:
        inactive = await repo.get_inactive_users(message.chat.id, cutoff)
        if not inactive:
            await message.reply(f"✅ Неактивных пользователей не найдено!")
            return

        kicked = 0
        for user_id in inactive[:50]:  # макс 50 за раз
            try:
                await message.bot.ban_chat_member(message.chat.id, user_id)
                await message.bot.unban_chat_member(message.chat.id, user_id)
                kicked += 1
            except Exception:
                pass

        await message.reply(f"👢 Кикнуто неактивных: <b>{kicked}</b> (не писали {days}+ дней)")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Дуэли ────────────────────────────────────────────────────────────────────

import random

# Активные дуэли: {(chat_id, target_id): (challenger_id, bet, msg_id)}
_duels: dict[tuple[int, int], tuple[int, int]] = {}

@router.message(F.text.regexp(CMD + r"дуэль(\s+\d+)?$", flags=2))
async def cmd_duel(message: Message) -> None:
    challenger = message.from_user
    await repo.get_or_create_user(challenger.id, challenger.username, challenger.full_name)

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "⚔️ Ответь на сообщение пользователя чтобы вызвать его на дуэль!\n"
            "Пример: <code>дуэль 100</code> (в ответ)"
        )
        return

    target = message.reply_to_message.from_user
    if target.is_bot or target.id == challenger.id:
        await message.reply("🤨 Некорректная цель!")
        return

    text = (message.text or "").strip()
    match = re.search(r"(\d+)$", text)
    bet = int(match.group(1)) if match else 50

    db_challenger = await repo.get_user(challenger.id)
    if not db_challenger or db_challenger.balance < bet:
        await message.reply(f"💸 Недостаточно ирисок! Нужно {bet} 🍬")
        return

    key = (message.chat.id, target.id)
    if key in _duels:
        await message.reply("⏳ У этого пользователя уже есть вызов на дуэль!")
        return

    _duels[key] = (challenger.id, bet)

    await message.reply(
        f"⚔️ {mention_user(challenger)} вызывает {mention_user(target)} на дуэль!\n"
        f"💰 Ставка: <b>{bet} 🍬</b>\n\n"
        f"{mention_user(target)}, напиши <b>принять</b> или <b>отказать</b> (60 сек.)"
    )

    await asyncio.sleep(60)
    if key in _duels:
        del _duels[key]
        try:
            await message.answer(f"⌛ Дуэль {mention_user(challenger)} vs {mention_user(target)} истекла.")
        except Exception:
            pass


@router.message(F.text.lower().in_({"принять", "отказать"}))
async def cmd_duel_response(message: Message) -> None:
    user = message.from_user
    key = (message.chat.id, user.id)
    if key not in _duels:
        return

    challenger_id, bet = _duels.pop(key)
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    if (message.text or "").lower() == "отказать":
        await message.reply(f"🏳️ {mention_user(user)} отказался от дуэли!")
        return

    db_challenger = await repo.get_user(challenger_id)
    db_target = await repo.get_user(user.id)

    if not db_challenger or db_challenger.balance < bet:
        await message.reply("❌ У вызывающего не хватает ирисок!")
        return
    if not db_target or db_target.balance < bet:
        await message.reply(f"❌ У {mention_user(user)} не хватает ирисок!")
        return

    # Бой!
    challenger_hp = random.randint(50, 100)
    target_hp = random.randint(50, 100)
    winner_id = challenger_id if challenger_hp >= target_hp else user.id
    loser_id = user.id if winner_id == challenger_id else challenger_id

    await repo.update_balance(winner_id, bet)
    await repo.update_balance(loser_id, -bet)

    challenger_mention = f'<a href="tg://user?id={challenger_id}">{db_challenger.full_name or challenger_id}</a>'
    winner_mention = challenger_mention if winner_id == challenger_id else mention_user(user)
    loser_mention = mention_user(user) if winner_id == challenger_id else challenger_mention

    await message.reply(
        f"⚔️ <b>Дуэль!</b>\n\n"
        f"❤️ {challenger_mention}: {challenger_hp} HP\n"
        f"❤️ {mention_user(user)}: {target_hp} HP\n\n"
        f"🏆 Победитель: {winner_mention}!\n"
        f"💰 Выигрыш: <b>{bet} 🍬</b>\n"
        f"💸 {loser_mention} проиграл {bet} 🍬"
    )


# ─── Заметки ──────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+заметка\s+\S+", flags=2))
async def cmd_add_note(message: Message) -> None:
    user = message.from_user
    text = (message.text or "")
    parts = text.split(None, 2)
    if len(parts) < 3:
        await message.reply("ℹ️ Пример: <code>+заметка название текст заметки</code>")
        return
    name = parts[1].lower()
    content = parts[2]
    await repo.add_note(user.id, message.chat.id, name, content)
    await message.reply(f"📝 Заметка <b>{name}</b> сохранена!")


@router.message(F.text.regexp(r"^-заметка\s+\S+", flags=2))
async def cmd_del_note(message: Message) -> None:
    user = message.from_user
    parts = (message.text or "").split(None, 1)
    name = parts[1].strip().lower() if len(parts) > 1 else ""
    ok = await repo.delete_note(user.id, message.chat.id, name)
    if ok:
        await message.reply(f"🗑️ Заметка <b>{name}</b> удалена.")
    else:
        await message.reply(f"❌ Заметка <b>{name}</b> не найдена.")


@router.message(F.text.regexp(r"^~заметка\s+\S+", flags=2))
async def cmd_edit_note(message: Message) -> None:
    user = message.from_user
    text = (message.text or "")
    parts = text.split(None, 2)
    if len(parts) < 3:
        await message.reply("ℹ️ Пример: <code>~заметка название новый текст</code>")
        return
    name = parts[1].lower()
    content = parts[2]
    ok = await repo.edit_note(user.id, message.chat.id, name, content)
    if ok:
        await message.reply(f"✏️ Заметка <b>{name}</b> обновлена!")
    else:
        await message.reply(f"❌ Заметка <b>{name}</b> не найдена.")


@router.message(F.text.regexp(r"^#заметка\s+\S+", flags=2))
async def cmd_get_note(message: Message) -> None:
    parts = (message.text or "").split(None, 1)
    name = parts[1].strip().lower() if len(parts) > 1 else ""
    note = await repo.get_note(message.from_user.id, message.chat.id, name)
    if note:
        await message.reply(f"📝 <b>{name}:</b>\n{note.content}")
    else:
        await message.reply(f"❌ Заметка <b>{name}</b> не найдена.")


@router.message(F.text.regexp(CMD + r"заметки$", flags=2))
async def cmd_list_notes(message: Message) -> None:
    notes = await repo.get_notes(message.from_user.id, message.chat.id)
    if not notes:
        await message.reply("📝 У тебя нет заметок.\nСоздай: <code>+заметка название текст</code>")
        return
    lines = ["📝 <b>Твои заметки:</b>\n"]
    for n in notes:
        preview = n.content[:40] + ("..." if len(n.content) > 40 else "")
        lines.append(f"• <b>{n.name}</b> — {preview}")
    lines.append("\nПосмотреть: <code>#заметка название</code>")
    await message.reply("\n".join(lines))
