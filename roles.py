"""
Модуль должностей и деревьев команд (ДК):
  /кто админ — список должностей
  !повысить / !понизить
  +дк N / -дк N — включить/выключить дерево
  !дк N M — установить минимальную должность для дерева
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from database import repo
from database.repo import ROLE_NAMES, TREE_NAMES
from utils.helpers import mention_user

logger = logging.getLogger(__name__)
router = Router()

# ─── Вспомогательная функция: проверка ДК ────────────────────────────────────

async def check_tree(message: Message, tree_num: int) -> bool:
    """
    Проверяет:
    1. Включено ли дерево команд
    2. Достаточно ли прав у пользователя
    Возвращает True если можно выполнять команду.
    """
    if message.chat.type == "private":
        return True

    tree = await repo.get_tree(message.chat.id, tree_num)

    if not tree.enabled:
        await message.reply(
            f"❌ ДК «{tree_num}» неактивно, чтобы включить: <code>+дк {tree_num}</code>"
        )
        return False

    user_role = await _get_effective_role(message)
    if user_role < tree.min_role:
        min_name = ROLE_NAMES.get(tree.min_role, str(tree.min_role))
        await message.reply(
            f"⛔ ДК «{TREE_NAMES.get(tree_num, tree_num)}» доступна для "
            f"<b>{min_name}</b> и выше."
        )
        return False

    return True


async def _get_effective_role(message: Message) -> int:
    """Возвращает эффективную должность: владелец чата всегда = 5."""
    user = message.from_user
    if not user:
        return 0
    try:
        member = await message.bot.get_chat_member(message.chat.id, user.id)
        if member.status == "creator":
            return 5
    except Exception:
        pass
    return await repo.get_user_role(user.id, message.chat.id)


# ─── /кто админ ───────────────────────────────────────────────────────────────

@router.message(Command("кто_админ"))
@router.message(F.text.lower() == "кто админ")
async def cmd_who_admin(message: Message) -> None:
    """Показывает всех участников с должностями."""
    if message.chat.type == "private":
        await message.reply("ℹ️ Команда работает только в группах.")
        return

    # Получаем тг-админов
    tg_admins = await message.bot.get_chat_administrators(message.chat.id)

    # Получаем должности из БД
    db_roles = await repo.get_all_roles(message.chat.id)
    role_map = {r.user_id: r.role for r in db_roles}

    lines = ["👑 <b>Администрация чата</b>\n"]

    # Сначала показываем владельца
    owner = next((a for a in tg_admins if a.status == "creator"), None)
    if owner:
        lines.append(f"⭐⭐⭐⭐⭐ <b>Владелец</b>")
        lines.append(f"  └ {mention_user(owner.user)}\n")

    # Участники с должностями из БД (4 и ниже)
    by_role: dict[int, list] = {4: [], 3: [], 2: [], 1: []}
    for r in db_roles:
        if r.role in by_role:
            user = await repo.get_user(r.user_id)
            name = user.full_name or user.username if user else str(r.user_id)
            by_role[r.role].append(name)

    role_labels = {
        4: "⭐⭐⭐⭐ Старший администратор",
        3: "⭐⭐⭐ Младший администратор",
        2: "⭐⭐ Старший модератор",
        1: "⭐ Младший модератор",
    }

    for role_num in [4, 3, 2, 1]:
        members = by_role[role_num]
        if members:
            lines.append(f"<b>{role_labels[role_num]}</b>")
            for m in members:
                lines.append(f"  └ {m}")
            lines.append("")

    # ДК статус
    lines.append("─────────────────")
    lines.append("📋 <b>Деревья команд:</b>")
    for num, name in TREE_NAMES.items():
        tree = await repo.get_tree(message.chat.id, num)
        status = "✅" if tree.enabled else "❌"
        min_role_name = ROLE_NAMES.get(tree.min_role, "—")
        lines.append(f"{status} ДК {num} — {name} | мин: {min_role_name}")

    await message.reply("\n".join(lines))


# ─── !повысить / !понизить ────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!повысить", flags=2))
async def cmd_promote(message: Message) -> None:
    actor_role = await _get_effective_role(message)
    if actor_role < 5:
        await message.reply("⛔ Повышать должности может только <b>Владелец</b>.")
        return

    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return

    if target.id == message.from_user.id:
        await message.reply("🤨 Нельзя повысить самого себя.")
        return

    parts = (message.text or "").split()
    current = await repo.get_user_role(target.id, message.chat.id)

    # Проверяем владелец ли цель
    try:
        member = await message.bot.get_chat_member(message.chat.id, target.id)
        if member.status == "creator":
            await message.reply("👑 Этот пользователь уже Владелец чата.")
            return
    except Exception:
        pass

    if len(parts) >= 2 and parts[1].isdigit():
        new_role = min(4, int(parts[1]))  # макс 4 (владелец = только creator)
    else:
        new_role = min(4, current + 1)

    if new_role <= current:
        await message.reply(f"ℹ️ Пользователь уже на должности {ROLE_NAMES.get(current)}.")
        return

    await repo.get_or_create_user(target.id, target.username, target.full_name)
    await repo.set_user_role(target.id, message.chat.id, new_role)
    logger.info(f"[PROMOTE] {target.id} → роль {new_role} в чате {message.chat.id}")

    await message.reply(
        f"⬆️ {mention_user(target)} повышен до <b>{ROLE_NAMES.get(new_role)}</b>!"
    )


@router.message(F.text.regexp(r"^!понизить", flags=2))
async def cmd_demote(message: Message) -> None:
    actor_role = await _get_effective_role(message)
    if actor_role < 5:
        await message.reply("⛔ Понижать должности может только <b>Владелец</b>.")
        return

    target = message.reply_to_message.from_user if message.reply_to_message else None
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return

    parts = (message.text or "").split()
    current = await repo.get_user_role(target.id, message.chat.id)

    if len(parts) >= 2 and parts[1].isdigit():
        new_role = max(0, int(parts[1]))
    else:
        new_role = max(0, current - 1)

    if new_role >= current:
        await message.reply(f"ℹ️ Пользователь уже на должности {ROLE_NAMES.get(current)}.")
        return

    await repo.set_user_role(target.id, message.chat.id, new_role)
    logger.info(f"[DEMOTE] {target.id} → роль {new_role} в чате {message.chat.id}")

    role_str = ROLE_NAMES.get(new_role, "Без должности")
    await message.reply(
        f"⬇️ {mention_user(target)} понижен до <b>{role_str}</b>."
    )


# ─── +дк / -дк ───────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+дк\s+\d+", flags=2))
async def cmd_enable_tree(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Управление ДК доступно только <b>Владельцу</b>.")
        return

    parts = (message.text or "").split()
    try:
        num = int(parts[1])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>+дк 1</code>")
        return

    if num not in TREE_NAMES:
        await message.reply(f"❌ ДК {num} не существует. Доступны: 1-6")
        return

    await repo.set_tree_enabled(message.chat.id, num, True)
    await message.reply(f"✅ ДК {num} «{TREE_NAMES[num]}» включено!")


@router.message(F.text.regexp(r"^\-дк\s+\d+", flags=2))
async def cmd_disable_tree(message: Message) -> None:
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Управление ДК доступно только <b>Владельцу</b>.")
        return

    parts = (message.text or "").split()
    try:
        num = int(parts[1])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>-дк 1</code>")
        return

    if num not in TREE_NAMES:
        await message.reply(f"❌ ДК {num} не существует. Доступны: 1-6")
        return

    await repo.set_tree_enabled(message.chat.id, num, False)
    await message.reply(f"❌ ДК {num} «{TREE_NAMES[num]}» отключено.")


# ─── !дк N M ─────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!дк\s+\d+\s+\d+", flags=2))
async def cmd_set_tree_role(message: Message) -> None:
    """!дк [номер_дк] [минимальная_должность]"""
    role = await _get_effective_role(message)
    if role < 5:
        await message.reply("⛔ Настройка ДК доступна только <b>Владельцу</b>.")
        return

    parts = (message.text or "").split()
    try:
        tree_num = int(parts[1])
        min_role = int(parts[2])
    except (IndexError, ValueError):
        await message.reply("ℹ️ Пример: <code>!дк 1 3</code>")
        return

    if tree_num not in TREE_NAMES:
        await message.reply(f"❌ ДК {tree_num} не существует. Доступны: 1-6")
        return

    if min_role < 0 or min_role > 5:
        await message.reply("❌ Должность от 0 до 5.")
        return

    await repo.set_tree_min_role(message.chat.id, tree_num, min_role)
    role_name = ROLE_NAMES.get(min_role, str(min_role))
    await message.reply(
        f"✅ ДК {tree_num} «{TREE_NAMES[tree_num]}» теперь доступно от <b>{role_name}</b> и выше."
    )
