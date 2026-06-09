"""
Должности, деревья команд, команда бот
"""
from __future__ import annotations
import logging
import re
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import repo
from database.repo import ROLE_NAMES, TREE_NAMES
from utils.helpers import mention_user

logger = logging.getLogger(__name__)
router = Router()


async def check_tree(message: Message, tree_num: int) -> bool:
    if message.chat.type == "private":
        return True
    tree = await repo.get_tree(message.chat.id, tree_num)
    if not tree.enabled:
        await message.reply(f"❌ ДК «{tree_num}» неактивно, чтобы включить: <code>+дк {tree_num}</code>")
        return False
    user_role = await _get_effective_role(message)
    if user_role < tree.min_role:
        min_name = ROLE_NAMES.get(tree.min_role, str(tree.min_role))
        await message.reply(f"⛔ ДК «{TREE_NAMES.get(tree_num, tree_num)}» доступна для <b>{min_name}</b> и выше.")
        return False
    return True


async def _get_effective_role(message: Message) -> int:
    user = message.from_user
    if not user:
        return 0
    db_role = await repo.get_user_role(user.id, message.chat.id)
    if db_role >= 5:
        return 5
    try:
        member = await message.bot.get_chat_member(message.chat.id, user.id)
        if member.status == "creator":
            all_roles = await repo.get_all_roles(message.chat.id)
            has_bot_owner = any(r.role == 5 for r in all_roles)
            if not has_bot_owner:
                return 5
    except Exception:
        pass
    return db_role


# ─── Команда БОТ ─────────────────────────────────────────────────────────────

@router.message(F.text.lower().in_({"бот", "!бот", ".бот", "bot", "!bot", ".bot"}))
async def cmd_bot_check(message: Message) -> None:
    await message.reply("✅ Бот здесь")


# ─── /кто админ ──────────────────────────────────────────────────────────────

@router.message(F.text.lower().in_({"кто админ", "!кто админ", ".кто админ"}))
@router.message(Command("кто_админ"))
async def cmd_who_admin(message: Message) -> None:
    if message.chat.type == "private":
        await message.reply("ℹ️ Команда работает только в группах.")
        return

    tg_admins = await message.bot.get_chat_administrators(message.chat.id)
    db_roles = await repo.get_all_roles(message.chat.id)

    lines = ["👑 <b>Администрация чата</b>\n"]

    # Владелец
    bot_owner = next((r for r in db_roles if r.role == 5), None)
    if bot_owner:
        u = await repo.get_user(bot_owner.user_id)
        name = u.full_name or u.username if u else str(bot_owner.user_id)
        lines.append(f"⭐⭐⭐⭐⭐ <b>Владелец</b>\n  └ {name}\n")
    else:
        owner = next((a for a in tg_admins if a.status == "creator"), None)
        if owner:
            lines.append(f"⭐⭐⭐⭐⭐ <b>Владелец</b>\n  └ {mention_user(owner.user)}\n")

    role_labels = {
        4: "⭐⭐⭐⭐ Старший администратор",
        3: "⭐⭐⭐ Младший администратор",
        2: "⭐⭐ Старший модератор",
        1: "⭐ Младший модератор",
    }
    by_role: dict[int, list] = {4: [], 3: [], 2: [], 1: []}
    for r in db_roles:
        if r.role in by_role:
            u = await repo.get_user(r.user_id)
            name = u.full_name or u.username if u else str(r.user_id)
            by_role[r.role].append(name)

    for role_num in [4, 3, 2, 1]:
        if by_role[role_num]:
            lines.append(f"<b>{role_labels[role_num]}</b>")
            for m in by_role[role_num]:
                lines.append(f"  └ {m}")
            lines.append("")

    await message.reply("\n".join(lines))


# ─── !дк — список ДК ─────────────────────────────────────────────────────────

@router.message(F.text.lower().in_({"!дк", ".дк", "дк"}))
async def cmd_show_trees(message: Message) -> None:
    lines = ["📋 <b>Деревья команд</b>\n"]
    for num in sorted(TREE_NAMES.keys()):
        tree = await repo.get_tree(message.chat.id, num)
        status = "✅" if tree.enabled else "❌"
        min_role_name = ROLE_NAMES.get(tree.min_role, "Все")
        lines.append(f"{status} <b>ДК {num}</b> — {TREE_NAMES[num]}")
        lines.append(f"   Мин: {min_role_name}")
    lines.append("\n<i>+дк N / -дк N / !дк N M</i>")
    await message.reply("\n".join(lines))


# ─── +дк / -дк ───────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+дк\s+\d+", flags=2))
async def cmd_enable_tree(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Только <b>Владелец</b>.")
        return
    parts = (message.text or "").split()
    try:
        num = int(parts[1])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>+дк 1</code>")
        return
    if num not in TREE_NAMES:
        await message.reply(f"❌ ДК {num} не существует. Доступны: 1-9")
        return
    await repo.set_tree_enabled(message.chat.id, num, True)
    await message.reply(f"✅ ДК {num} «{TREE_NAMES[num]}» включено!")


@router.message(F.text.regexp(r"^\-дк\s+\d+", flags=2))
async def cmd_disable_tree(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Только <b>Владелец</b>.")
        return
    parts = (message.text or "").split()
    try:
        num = int(parts[1])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>-дк 1</code>")
        return
    if num not in TREE_NAMES:
        await message.reply(f"❌ ДК {num} не существует. Доступны: 1-9")
        return
    await repo.set_tree_enabled(message.chat.id, num, False)
    await message.reply(f"❌ ДК {num} «{TREE_NAMES[num]}» отключено.")


# ─── !дк N M ─────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^[!.]?дк\s+\d+\s+\d+", flags=2))
async def cmd_set_tree_role(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Только <b>Владелец</b>.")
        return
    text = re.sub(r'^[!.]', '', message.text or '').strip()
    parts = text.split()
    try:
        tree_num = int(parts[1])
        min_role = int(parts[2])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>!дк 1 3</code>")
        return
    if tree_num not in TREE_NAMES:
        await message.reply(f"❌ ДК {tree_num} не существует.")
        return
    if not 0 <= min_role <= 5:
        await message.reply("❌ Должность от 0 до 5.")
        return
    await repo.set_tree_min_role(message.chat.id, tree_num, min_role)
    await message.reply(f"✅ ДК {tree_num} «{TREE_NAMES[tree_num]}» — мин. должность: <b>{ROLE_NAMES[min_role]}</b>")


# ─── !повысить / !понизить ───────────────────────────────────────────────────

@router.message(F.text.regexp(r"^[!.]?повысить", flags=2))
async def cmd_promote(message: Message) -> None:
    actor_role = await _get_effective_role(message)
    if actor_role < 5:
        await message.reply("⛔ Повышать может только <b>Владелец</b>.")
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    if target.id == message.from_user.id:
        await message.reply("🤨 Нельзя повысить самого себя.")
        return
    try:
        member = await message.bot.get_chat_member(message.chat.id, target.id)
        if member.status == "creator":
            await message.reply("👑 Это владелец чата.")
            return
    except Exception:
        pass
    text = re.sub(r'^[!.]', '', message.text or '').strip()
    parts = text.split()
    current = await repo.get_user_role(target.id, message.chat.id)
    new_role = min(4, int(parts[1])) if len(parts) >= 2 and parts[1].isdigit() else min(4, current + 1)
    if new_role <= current:
        await message.reply(f"ℹ️ Уже на должности {ROLE_NAMES.get(current)}.")
        return
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    await repo.set_user_role(target.id, message.chat.id, new_role)
    await message.reply(f"⬆️ {mention_user(target)} повышен до <b>{ROLE_NAMES[new_role]}</b>!")


@router.message(F.text.regexp(r"^[!.]?понизить", flags=2))
async def cmd_demote(message: Message) -> None:
    actor_role = await _get_effective_role(message)
    if actor_role < 5:
        await message.reply("⛔ Понижать может только <b>Владелец</b>.")
        return
    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    text = re.sub(r'^[!.]', '', message.text or '').strip()
    parts = text.split()
    current = await repo.get_user_role(target.id, message.chat.id)
    new_role = max(0, int(parts[1])) if len(parts) >= 2 and parts[1].isdigit() else max(0, current - 1)
    if new_role >= current:
        await message.reply(f"ℹ️ Уже на должности {ROLE_NAMES.get(current)}.")
        return
    await repo.set_user_role(target.id, message.chat.id, new_role)
    await message.reply(f"⬇️ {mention_user(target)} понижен до <b>{ROLE_NAMES.get(new_role, 'Без должности')}</b>.")


# ─── /передать ───────────────────────────────────────────────────────────────

_transfer_pending: dict[tuple[int, int], int] = {}


@router.message(F.text.regexp(r"^[/!.]?передать", flags=2))
async def cmd_transfer_owner(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Только <b>Владелец</b> может передать права.")
        return
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        parts = (message.text or "").split()
        if len(parts) >= 2:
            username = parts[1].lstrip("@")
            from sqlalchemy import select as sa_select
            from database.db import User as UserModel, async_session
            async with async_session() as s:
                result = await s.execute(sa_select(UserModel).where(func.lower(UserModel.username) == username.lower()))
                u = result.scalar_one_or_none()
                if u:
                    class FakeUser:
                        def __init__(self, db_u):
                            self.id = db_u.id
                            self.full_name = db_u.full_name
                            self.username = db_u.username
                    target = FakeUser(u)
    if not target:
        await message.reply("ℹ️ Использование: /передать @юзернейм или ответь на сообщение")
        return
    if target.id == message.from_user.id:
        await message.reply("🤨 Нельзя передать самому себе.")
        return
    _transfer_pending[(message.chat.id, message.from_user.id)] = target.id
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Да", callback_data=f"transfer_yes:{message.from_user.id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"transfer_no:{message.from_user.id}"),
    ]])
    tname = f"@{target.username}" if target.username else target.full_name
    await message.reply(
        f"⚠️ Передать права <b>Владельца</b> пользователю <b>{tname}</b>?\n\nЭто действие необратимо!",
        reply_markup=kb
    )


@router.callback_query(F.data.startswith("transfer_yes:"))
async def cb_transfer_yes(call: CallbackQuery) -> None:
    from_id = int(call.data.split(":")[1])
    if call.from_user.id != from_id:
        await call.answer("⛔ Не твоя кнопка!", show_alert=True)
        return
    key = (call.message.chat.id, from_id)
    target_id = _transfer_pending.pop(key, None)
    if not target_id:
        await call.answer("⏳ Запрос устарел.", show_alert=True)
        return
    await repo.set_user_role(from_id, call.message.chat.id, 4)
    await repo.set_user_role(target_id, call.message.chat.id, 5)
    target = await repo.get_user(target_id)
    tname = target.full_name or target.username if target else str(target_id)
    await call.message.edit_text(f"👑 Права <b>Владельца</b> переданы <b>{tname}</b>!")
    await call.answer()


@router.callback_query(F.data.startswith("transfer_no:"))
async def cb_transfer_no(call: CallbackQuery) -> None:
    from_id = int(call.data.split(":")[1])
    if call.from_user.id != from_id:
        await call.answer("⛔ Не твоя кнопка!", show_alert=True)
        return
    _transfer_pending.pop((call.message.chat.id, from_id), None)
    await call.message.edit_text("❌ Передача отменена.")
    await call.answer()
