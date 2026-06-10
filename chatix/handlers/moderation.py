"""
Модерация Chatix — поддерживает префиксы ! . и без префикса
"""
from __future__ import annotations
import asyncio
import logging
import re
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import ChatPermissions, Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from config import settings
from database import repo
from utils.helpers import extract_target, mention_user, parse_duration

logger = logging.getLogger(__name__)
router = Router()


def cmd_pattern(name: str) -> str:
    """Паттерн для команды с префиксами ! . или без"""
    return rf"^([!.])?{name}(\s|$)"


def admin_only(handler):
    async def wrapper(message: Message, is_admin: bool = False, **kwargs):
        if not is_admin:
            await message.reply("⛔ Эта команда доступна только администраторам!")
            return
        return await handler(message, is_admin=is_admin, **kwargs)
    return wrapper


def _parse_reason(text: str, cmd: str) -> str:
    # Убираем префикс !/.
    clean = re.sub(r'^[!.]', '', text).strip()
    after = clean[len(cmd):].strip()
    return after if after else "Нет причины"


def _format_duration(td: timedelta) -> str:
    total = int(td.total_seconds())
    if total < 3600: return f"{total // 60} мин."
    if total < 86400: return f"{total // 3600} ч."
    return f"{total // 86400} д."


@router.message(F.text.regexp(cmd_pattern("бан"), flags=2))
@admin_only
async def cmd_ban(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    reason = _parse_reason(message.text, "бан")
    try:
        await message.chat.ban(target.id)
        logger.info(f"[BAN] {target.id} в {message.chat.id}")
        await message.reply(f"🔨 {mention_user(target)} заблокирован.\n📝 Причина: <i>{reason}</i>")
    except Exception as e:
        await message.reply(f"❌ Не удалось забанить: {e}")


@router.message(F.text.regexp(cmd_pattern("кик"), flags=2))
@admin_only
async def cmd_kick(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    reason = _parse_reason(message.text, "кик")
    try:
        await message.chat.ban(target.id)
        await message.chat.unban(target.id)
        await message.reply(f"👟 {mention_user(target)} выгнан.\n📝 Причина: <i>{reason}</i>")
    except Exception as e:
        await message.reply(f"❌ Не удалось кикнуть: {e}")


@router.message(F.text.regexp(cmd_pattern("мут"), flags=2))
@admin_only
async def cmd_mute(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    text_clean = re.sub(r'^[!.]', '', message.text).strip()
    parts = text_clean.split(maxsplit=2)
    duration = timedelta(minutes=settings.DEFAULT_MUTE_MINUTES)
    reason = "Нет причины"
    if len(parts) >= 2:
        parsed = parse_duration(parts[1])
        if parsed:
            duration = parsed
            reason = parts[2] if len(parts) >= 3 else reason
        else:
            reason = " ".join(parts[1:])
    import time
    until_timestamp = int(time.time()) + int(duration.total_seconds())
    silence = ChatPermissions(can_send_messages=False)
    try:
        await message.bot.restrict_chat_member(message.chat.id, target.id, permissions=silence, until_date=until_timestamp)
        await message.reply(f"🔇 {mention_user(target)} заглушён на <b>{_format_duration(duration)}</b>.\n📝 Причина: <i>{reason}</i>")
        async def notify_unmute():
            await asyncio.sleep(duration.total_seconds())
            try:
                uname = f"@{target.username}" if target.username else mention_user(target)
                await message.bot.send_message(message.chat.id, f"🔊 {uname}, теперь вы снова можете общаться! Лучше следите за языком..")
            except Exception:
                pass
        asyncio.create_task(notify_unmute())
    except Exception as e:
        await message.reply(f"❌ Не удалось замутить: {e}")


@router.message(F.text.regexp(cmd_pattern("анмут"), flags=2))
@admin_only
async def cmd_unmute(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    full_perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
    try:
        await message.bot.restrict_chat_member(message.chat.id, target.id, permissions=full_perms)
        await message.reply(f"🔊 {mention_user(target)} снова может писать.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(F.text.regexp(cmd_pattern("варн"), flags=2))
@admin_only
async def cmd_warn(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    reason = _parse_reason(message.text, "варн")
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    warn_count = await repo.add_warning(target.id, message.chat.id, reason, message.from_user.id)
    if warn_count >= settings.MAX_WARNINGS:
        try:
            await message.chat.ban(target.id)
            await repo.clear_warnings(target.id, message.chat.id)
            await message.reply(f"🔨 {mention_user(target)} получил {warn_count} предупреждений и забанен!")
        except Exception as e:
            await message.reply(f"⚠️ {warn_count}/{settings.MAX_WARNINGS} варнов, но забанить не вышло: {e}")
    else:
        await message.reply(f"⚠️ {mention_user(target)} получает предупреждение (<b>{warn_count}/{settings.MAX_WARNINGS}</b>).\n📝 Причина: <i>{reason}</i>")


@router.message(F.text.regexp(cmd_pattern("разбан"), flags=2))
@admin_only
async def cmd_unban(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        await message.reply(f"✅ {mention_user(target)} разбанен.")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@router.message(F.text.regexp(cmd_pattern("вернуть"), flags=2))
@admin_only
async def cmd_return(message: Message, **_) -> None:
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение пользователя.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        link = await message.bot.create_chat_invite_link(message.chat.id, member_limit=1)
        try:
            await message.bot.send_message(target.id, f"✅ Тебя разбанили в <b>{message.chat.title}</b>!\nСсылка: {link.invite_link}")
            await message.reply(f"✅ {mention_user(target)} разбанен, ссылка отправлена в личку.")
        except Exception:
            await message.reply(f"✅ {mention_user(target)} разбанен!\nСсылка: {link.invite_link}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── Созвать всех ─────────────────────────────────────────────────────────────

@router.message(F.text.regexp(r"^[!.]?созвать\s+всех", flags=2))
@admin_only
async def cmd_summon(message: Message, **_) -> None:
    text = (message.text or "").strip()
    # Извлекаем сообщение после команды
    match = re.match(r"^[!.]?созвать\s+всех\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    summon_msg = match.group(1).strip() if match else ""

    try:
        members = await message.bot.get_chat_administrators(message.chat.id)
        mentions = []
        for m in members:
            if not m.user.is_bot:
                mentions.append(mention_user(m.user))

        text_out = "📢 <b>Созыв всех участников!</b>"
        if summon_msg:
            text_out += f"\n\n💬 {summon_msg}"
        if mentions:
            text_out += "\n\n" + " ".join(mentions)

        await message.reply(text_out)
        logger.info(f"[SUMMON] {message.from_user.id} созвал всех в {message.chat.id}")
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


# ─── +правила / +приветствие ─────────────────────────────────────────────────

@router.message(F.text.regexp(r"^\+правила", flags=2))
async def cmd_plus_rules(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    value = (message.text or "")[len("+правила"):].strip()
    if not value:
        await message.reply("ℹ️ Пример: +правила Не спамить")
        return
    await repo.update_chat_settings(message.chat.id, rules=value)
    await message.reply("✅ Правила чата обновлены!")


@router.message(F.text.regexp(r"^\+приветствие", flags=2))
async def cmd_plus_welcome(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    value = (message.text or "")[len("+приветствие"):].strip()
    if not value:
        await message.reply("ℹ️ Пример: +приветствие Привет!")
        return
    await repo.update_chat_settings(message.chat.id, welcome_message=value)
    await message.reply("✅ Приветствие обновлено!")


# ─── Приветствие новых участников ─────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_new_member(event: ChatMemberUpdated) -> None:
    user = event.new_chat_member.user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    cs = await repo.get_chat_settings(event.chat.id)
    welcome = cs.welcome_message or f"👋 Добро пожаловать, {mention_user(user)}!\nНапиши /правила для ознакомления с правилами."
    try:
        await event.bot.send_message(event.chat.id, welcome)
    except Exception as e:
        logger.warning(f"Не удалось отправить приветствие: {e}")


# ─── Автофильтр ───────────────────────────────────────────────────────────────

@router.message(F.text & ~F.text.startswith("/") & ~F.text.startswith("!") & ~F.text.startswith("+") & ~F.text.startswith("-") & ~F.text.startswith("."))
async def auto_filter(message: Message) -> None:
    if not message.from_user or message.chat.type == "private":
        return
    cs = await repo.get_chat_settings(message.chat.id)
    text_lower = (message.text or "").lower()
    forbidden = set(settings.FORBIDDEN_WORDS)
    if cs.forbidden_words:
        forbidden.update(cs.forbidden_words.split("|"))
    for word in forbidden:
        if word and word in text_lower:
            try:
                await message.delete()
                await message.answer(f"🚫 {mention_user(message.from_user)}, запрещённое слово удалено.")
            except Exception:
                pass
            return
    if cs.block_links:
        from utils.helpers import contains_link
        if contains_link(message.text or ""):
            try:
                await message.delete()
                await message.answer(f"🔗 {mention_user(message.from_user)}, ссылки запрещены.")
            except Exception:
                pass
            return
    await repo.get_or_create_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    await repo.increment_messages(message.from_user.id)
    await repo.record_daily_activity(message.from_user.id, message.chat.id)
