"""
ДК 13 — Кланы | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import format_balance, mention_user

router = Router()
CMD = r"^[/!.]?"


@router.message(F.text.regexp(CMD + r"клан(\s|$)", flags=re.IGNORECASE))
async def cmd_clan_info(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    clan, _ = await repo.get_user_clan(user.id, message.chat.id)
    if not clan:
        await message.reply(
            "🏰 <b>Кланы</b>\n\nТы не в клане.\n\n"
            "<i>создать_клан [название] — 500 ирисок\n"
            "вступить_клан [название]</i>"
        )
        return
    members = await repo.get_clan_members(clan.id)
    owner = await repo.get_user(clan.owner_id)
    owner_name = (owner.full_name or owner.username) if owner else str(clan.owner_id)
    await message.reply(
        f"🏰 <b>Клан {clan.name}</b>\n\n"
        f"👑 Основатель: {owner_name}\n"
        f"👥 Участников: {len(members)}\n"
        f"💰 Казна: {format_balance(clan.balance)}\n"
        f"📅 Создан: {clan.created_at.strftime('%d.%m.%Y')}"
    )


@router.message(F.text.regexp(CMD + r"создать_клан(\s|$)", flags=re.IGNORECASE))
async def cmd_create_clan(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("ℹ️ Использование: <code>создать_клан [название]</code>\nСтоимость: 500 ирисок")
        return
    name = parts[1].strip()
    if len(name) > 32:
        await message.reply("❌ Название не более 32 символов.")
        return
    ok, result = await repo.create_clan(message.chat.id, user.id, name)
    if ok:
        await repo.award_achievement(user.id, "clan_created")
        await message.reply(f"🏰 Клан <b>{name}</b> создан! Потрачено 500 ирисок.")
    else:
        await message.reply(f"❌ {result}")


@router.message(F.text.regexp(CMD + r"вступить_клан(\s|$)", flags=re.IGNORECASE))
async def cmd_join_clan(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("ℹ️ Использование: <code>вступить_клан [название]</code>")
        return
    name = parts[1].strip()
    clan = await repo.get_clan_by_name(message.chat.id, name)
    if not clan:
        await message.reply("❌ Клан не найден.")
        return
    ok, msg = await repo.join_clan(clan.id, user.id)
    if ok:
        await message.reply(f"✅ {mention_user(user)} вступил в клан <b>{name}</b>!")
    else:
        await message.reply(f"❌ {msg}")


@router.message(F.text.regexp(CMD + r"выйти_клан(\s|$)", flags=re.IGNORECASE))
async def cmd_leave_clan(message: Message) -> None:
    user = message.from_user
    ok = await repo.leave_clan(user.id, message.chat.id)
    if ok:
        await message.reply(f"👋 {mention_user(user)} покинул клан.")
    else:
        await message.reply("❌ Ты не в клане.")


@router.message(F.text.regexp(CMD + r"кланы(\s|$)", flags=re.IGNORECASE))
async def cmd_all_clans(message: Message) -> None:
    clans = await repo.get_all_clans(message.chat.id)
    if not clans:
        await message.reply("🏰 В этом чате нет кланов.")
        return
    lines = ["🏰 <b>Кланы чата</b>\n"]
    for c in clans:
        members = await repo.get_clan_members(c.id)
        lines.append(f"• <b>{c.name}</b> — {len(members)} участн. | 💰 {format_balance(c.balance)}")
    await message.reply("\n".join(lines))
