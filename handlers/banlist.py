"""
Глобальная база нарушителей
Только для владельца бота (ID: 6647482475)
!занести в базу [причина] — добавить (ответ на сообщение)
.база — просмотр базы с кнопкой удаления
"""
from __future__ import annotations
import logging
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import repo

logger = logging.getLogger(__name__)
router = Router()

BOT_OWNER_ID = 6647482475


def is_owner(user_id: int) -> bool:
    return user_id == BOT_OWNER_ID


@router.message(F.text.regexp(r"^[!.]?занести\s+в\s+базу", flags=2))
async def cmd_add_to_banlist(message: Message) -> None:
    if not is_owner(message.from_user.id):
        await message.reply("⛔ Эта команда доступна только владельцу бота.")
        return

    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user

    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return

    import re
    text = message.text or ""
    match = re.match(r"^[!.]?занести\s+в\s+базу\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    reason = match.group(1).strip() if match else "Нет причины"

    ok = await repo.add_to_banlist(target.id, reason, message.from_user.id)
    if not ok:
        await message.reply(f"ℹ️ Пользователь уже в базе.")
        return

    # Баним во всех чатах где есть бот — пытаемся забанить в текущем
    try:
        await message.chat.ban(target.id)
    except Exception:
        pass

    logger.info(f"[BANLIST] {target.id} добавлен в базу владельцем")
    await message.reply(
        f"✅ Пользователь <b>{target.full_name}</b> (ID: <code>{target.id}</code>) "
        f"занесён в базу нарушителей!\n"
        f"📝 Причина: <i>{reason}</i>"
    )


@router.message(F.text.lower().in_({".база", "!база", "база"}))
async def cmd_view_banlist(message: Message) -> None:
    if not is_owner(message.from_user.id):
        await message.reply("⛔ Эта команда доступна только владельцу бота.")
        return

    entries = await repo.get_banlist()
    if not entries:
        await message.reply("📋 База нарушителей пуста.")
        return

    for i, entry in enumerate(entries, 1):
        user = await repo.get_user(entry.user_id)
        name = user.full_name or user.username if user else str(entry.user_id)
        date = entry.created_at.strftime("%d.%m.%Y")
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Удалить из базы", callback_data=f"unban_base:{entry.user_id}")
        ]])
        await message.answer(
            f"<b>{i}. {name}</b>\n"
            f"ID: <code>{entry.user_id}</code>\n"
            f"📝 {entry.reason}\n"
            f"📅 {date}",
            reply_markup=kb
        )


@router.callback_query(F.data.startswith("unban_base:"))
async def cb_unban_base(call: CallbackQuery) -> None:
    if not is_owner(call.from_user.id):
        await call.answer("⛔ Только для владельца бота!", show_alert=True)
        return

    user_id = int(call.data.split(":")[1])
    ok = await repo.remove_from_banlist(user_id)
    if ok:
        await call.message.edit_text(f"✅ Пользователь <code>{user_id}</code> удалён из базы.")
        logger.info(f"[BANLIST] {user_id} удалён из базы")
    else:
        await call.answer("Не найден в базе.", show_alert=True)
    await call.answer()


# ─── Автобан при входе в чат ─────────────────────────────────────────────────

async def check_banlist_on_join(user_id: int, chat_id: int, bot) -> bool:
    """Вызывается при входе пользователя — банит если в базе."""
    if await repo.is_in_banlist(user_id):
        try:
            await bot.ban_chat_member(chat_id, user_id)
            logger.info(f"[BANLIST AUTO] {user_id} забанен автоматически в {chat_id}")
            return True
        except Exception as e:
            logger.warning(f"Не удалось автобанить {user_id}: {e}")
    return False
