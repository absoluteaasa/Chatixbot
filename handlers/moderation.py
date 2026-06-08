"""
Модуль модерации:
  !бан, !кик, !мут, !варн
  Автофильтр спама, запрещённых слов, ссылок
  Приветствие новых участников
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    ChatPermissions, Message, ChatMemberUpdated,
)
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, JOIN_TRANSITION

from config import settings
from database import repo
from utils.helpers import extract_target, mention_user, parse_duration

logger = logging.getLogger(__name__)
router = Router()

# ─── Декоратор проверки прав ──────────────────────────────────────────────────

def admin_only(handler):
    """Декоратор: выполняет handler только если is_admin=True в data."""
    async def wrapper(message: Message, is_admin: bool = False, **kwargs):
        if not is_admin:
            await message.reply("⛔ Эта команда доступна только администраторам!")
            return
        return await handler(message, is_admin=is_admin, **kwargs)
    return wrapper


# ─── Бан ──────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!бан", flags=2))
@admin_only
async def cmd_ban(message: Message, **_) -> None:
    """!бан [причина] — навсегда блокирует пользователя (ответ на сообщение)."""
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя, которого хочешь забанить.")
        return

    reason = _parse_reason(message.text, prefix="!бан")

    try:
        await message.chat.ban(target.id)
        logger.info(f"[BAN] {target.id} в чате {message.chat.id} причина: {reason}")
        await message.reply(
            f"🔨 {mention_user(target)} заблокирован навсегда.\n"
            f"📝 Причина: <i>{reason}</i>"
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось забанить: {e}")


# ─── Кик ──────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!кик", flags=2))
@admin_only
async def cmd_kick(message: Message, **_) -> None:
    """!кик [причина] — удаляет пользователя из чата."""
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя, которого хочешь кикнуть.")
        return

    reason = _parse_reason(message.text, prefix="!кик")

    try:
        await message.chat.ban(target.id)
        await message.chat.unban(target.id)  # разбан сразу = кик
        logger.info(f"[KICK] {target.id} из чата {message.chat.id} причина: {reason}")
        await message.reply(
            f"👟 {mention_user(target)} выгнан из чата.\n"
            f"📝 Причина: <i>{reason}</i>"
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось кикнуть: {e}")


# ─── Мут ──────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!мут", flags=2))
@admin_only
async def cmd_mute(message: Message, **_) -> None:
    """
    !мут [время: 10m/2h/1d] [причина]
    Если время не указано — мутит на 10 минут.
    """
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя, которого хочешь замутить.")
        return

    parts = message.text.split(maxsplit=2)  # ['!мут', '10m', 'причина']
    duration = timedelta(minutes=settings.DEFAULT_MUTE_MINUTES)
    reason = "Нет причины"

    if len(parts) >= 2:
        parsed = parse_duration(parts[1])
        if parsed:
            duration = parsed
            reason = parts[2] if len(parts) >= 3 else reason
        else:
            reason = " ".join(parts[1:])

    until = datetime.utcnow() + duration
    silence = ChatPermissions(can_send_messages=False)

    try:
        await message.bot.restrict_chat_member(
            message.chat.id, target.id, permissions=silence, until_date=until
        )
        logger.info(f"[MUTE] {target.id} в чате {message.chat.id} на {duration}")
        await message.reply(
            f"🔇 {mention_user(target)} заглушён на <b>{_format_duration(duration)}</b>.\n"
            f"📝 Причина: <i>{reason}</i>"
        )
    except Exception as e:
        await message.reply(f"❌ Не удалось замутить: {e}")


# ─── Анмут ────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!анмут", flags=2))
@admin_only
async def cmd_unmute(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return

    full_perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )
    try:
        await message.bot.restrict_chat_member(message.chat.id, target.id, permissions=full_perms)
        await message.reply(f"🔊 {mention_user(target)} снова может писать.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Варн ─────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!варн", flags=2))
@admin_only
async def cmd_warn(message: Message, **_) -> None:
    """!варн [причина] — выдаёт предупреждение. При MAX_WARNINGS варнах — автобан."""
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return

    reason = _parse_reason(message.text, prefix="!варн")
    await repo.get_or_create_user(target.id, target.username, target.full_name)

    warn_count = await repo.add_warning(target.id, message.chat.id, reason, message.from_user.id)
    logger.info(f"[WARN] {target.id} в чате {message.chat.id}: {warn_count}/{settings.MAX_WARNINGS}")

    if warn_count >= settings.MAX_WARNINGS:
        try:
            await message.chat.ban(target.id)
            await repo.clear_warnings(target.id, message.chat.id)
            await message.reply(
                f"🔨 {mention_user(target)} получил <b>{warn_count}</b> предупреждений и забанен автоматически!"
            )
        except Exception as e:
            await message.reply(f"⚠️ {warn_count}/{settings.MAX_WARNINGS} варнов, но забанить не вышло: {e}")
    else:
        await message.reply(
            f"⚠️ {mention_user(target)} получает предупреждение "
            f"(<b>{warn_count}/{settings.MAX_WARNINGS}</b>).\n"
            f"📝 Причина: <i>{reason}</i>"
        )


# ─── Приветствие новых участников ─────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_new_member(event: ChatMemberUpdated) -> None:
    user = event.new_chat_member.user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    chat_settings = await repo.get_chat_settings(event.chat.id)
    welcome = chat_settings.welcome_message or (
        f"👋 Добро пожаловать, {mention_user(user)}!\n"
        f"Рады видеть тебя в нашем чате. Напиши /правила, чтобы ознакомиться с правилами."
    )
    try:
        await event.bot.send_message(event.chat.id, welcome)
        logger.info(f"[JOIN] Новый участник: {user.id} в чате {event.chat.id}")
    except Exception as e:
        logger.warning(f"Не удалось отправить приветствие: {e}")


# ─── Команда /правила ─────────────────────────────────────────────────────────

@router.message(Command("правила"))
async def cmd_rules(message: Message) -> None:
    chat_settings = await repo.get_chat_settings(message.chat.id)
    rules = chat_settings.rules or (
        "📜 <b>Правила чата:</b>\n"
        "1. Уважайте друг друга\n"
        "2. Не спамьте\n"
        "3. Не рекламируйте\n"
        "4. Следуйте указаниям администраторов"
    )
    await message.reply(rules)


# ─── Автофильтр сообщений ─────────────────────────────────────────────────────

@router.message(F.text)
async def auto_filter(message: Message) -> None:
    """Проверяет каждое сообщение на запрещённые слова и ссылки."""
    if not message.from_user or message.chat.type == "private":
        return

    chat_settings = await repo.get_chat_settings(message.chat.id)
    text_lower = (message.text or "").lower()

    # Проверка запрещённых слов (из настроек + из дефолтного списка)
    forbidden = set(settings.FORBIDDEN_WORDS)
    if chat_settings.forbidden_words:
        forbidden.update(chat_settings.forbidden_words.split("|"))

    for word in forbidden:
        if word and word in text_lower:
            try:
                await message.delete()
                await message.answer(
                    f"🚫 {mention_user(message.from_user)}, запрещённое слово удалено."
                )
            except Exception:
                pass
            return

    # Проверка ссылок
    if chat_settings.block_links:
        from utils.helpers import contains_link
        if contains_link(message.text or ""):
            try:
                await message.delete()
                await message.answer(f"🔗 {mention_user(message.from_user)}, ссылки запрещены в этом чате.")
            except Exception:
                pass
            return

    # Считаем сообщения для статистики
    await repo.get_or_create_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    await repo.increment_messages(message.from_user.id)
    await repo.record_daily_activity(message.from_user.id, message.chat.id)


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def _parse_reason(text: str, prefix: str) -> str:
    """Извлекает причину из команды типа '!варн нарушение правил'."""
    after = text[len(prefix):].strip()
    return after if after else "Нет причины"


def _format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 3600:
        return f"{total // 60} мин."
    if total < 86400:
        return f"{total // 3600} ч."
    return f"{total // 86400} д."


# ─── Разбан ───────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^!разбан", flags=2))
@admin_only
async def cmd_unban(message: Message, **_) -> None:
    """!разбан — снимает бан (ответ на сообщение)."""
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        logger.info(f"[UNBAN] {target.id} в чате {message.chat.id}")
        await message.reply(f"✅ {mention_user(target)} разбанен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Вернуть (разбан + инвайт) ───────────────────────────────────────────────

@router.message(F.text.regexp(r"^!вернуть", flags=2))
@admin_only
async def cmd_return(message: Message, **_) -> None:
    """!вернуть — разбанивает и отправляет ссылку на чат."""
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        # Создаём одноразовую инвайт-ссылку
        link = await message.bot.create_chat_invite_link(
            message.chat.id, member_limit=1
        )
        # Отправляем ссылку в личку
        try:
            await message.bot.send_message(
                target.id,
                f"✅ Тебя разбанили в чате <b>{message.chat.title}</b>!\n"
                f"Вот ссылка для возврата: {link.invite_link}"
            )
            await message.reply(f"✅ {mention_user(target)} разбанен, ссылка отправлена в личку.")
        except Exception:
            await message.reply(
                f"✅ {mention_user(target)} разбанен!\n"
                f"Ссылка (не смог отправить в личку): {link.invite_link}"
            )
        logger.info(f"[RETURN] {target.id} в чате {message.chat.id}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── +правила / +приветствие ─────────────────────────────────────────────────

@router.message(F.text.lower().regexp(r"^\+правила\s+.+", flags=2))
async def cmd_plus_rules(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    text = (message.text or "")
    value = text[len("+правила"):].strip()
    await repo.update_chat_settings(message.chat.id, rules=value)
    await message.reply("✅ Правила чата обновлены!")


@router.message(F.text.lower().regexp(r"^\+приветствие\s+.+", flags=2))
async def cmd_plus_welcome(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    text = (message.text or "")
    value = text[len("+приветствие"):].strip()
    await repo.update_chat_settings(message.chat.id, welcome_message=value)
    await message.reply("✅ Приветствие обновлено!")
