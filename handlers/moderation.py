"""Модерация Chatix — ! . / или без префикса"""
from __future__ import annotations
import asyncio, logging, re
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import ChatPermissions, Message, ChatMemberUpdated
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from config import settings
from database import repo
from utils.helpers import extract_target, mention_user, parse_duration
from handlers.banlist import check_banlist_on_join

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

def get_reason(text: str, cmd: str) -> str:
    clean = re.sub(r'^[/!.]', '', text).strip()
    after = clean[len(cmd):].strip()
    return after if after else "Нет причины"

def fmt_dur(td: timedelta) -> str:
    t = int(td.total_seconds())
    if t < 3600: return f"{t//60} мин."
    if t < 86400: return f"{t//3600} ч."
    return f"{t//86400} д."


@router.message(F.text.regexp(CMD + r"бан(\s|$)", flags=2))
@admin_only
async def cmd_ban(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    reason = get_reason(message.text, "бан")
    try:
        await message.chat.ban(target.id)
        await message.reply(f"🔨 {mention_user(target)} заблокирован.\n📝 <i>{reason}</i>")
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"кик(\s|$)", flags=2))
@admin_only
async def cmd_kick(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    reason = get_reason(message.text, "кик")
    try:
        await message.chat.ban(target.id)
        await message.chat.unban(target.id)
        await message.reply(f"👟 {mention_user(target)} выгнан.\n📝 <i>{reason}</i>")
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"мут(\s|$)", flags=2))
@admin_only
async def cmd_mute(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    clean = re.sub(r'^[/!.]', '', message.text).strip()
    parts = clean.split(maxsplit=2)
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
    until_ts = int(time.time()) + int(duration.total_seconds())
    try:
        await message.bot.restrict_chat_member(message.chat.id, target.id, permissions=ChatPermissions(can_send_messages=False), until_date=until_ts)
        await message.reply(f"🔇 {mention_user(target)} заглушён на <b>{fmt_dur(duration)}</b>.\n📝 <i>{reason}</i>")
        async def notify():
            await asyncio.sleep(duration.total_seconds())
            try:
                uname = f"@{target.username}" if target.username else mention_user(target)
                await message.bot.send_message(message.chat.id, f"🔊 {uname}, теперь вы снова можете общаться! Лучше следите за языком..")
            except Exception:
                pass
        asyncio.create_task(notify())
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"анмут(\s|$)", flags=2))
@admin_only
async def cmd_unmute(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    perms = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_add_web_page_previews=True)
    try:
        await message.bot.restrict_chat_member(message.chat.id, target.id, permissions=perms)
        await message.reply(f"🔊 {mention_user(target)} размучен.")
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"варн(\s|$)", flags=2))
@admin_only
async def cmd_warn(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    reason = get_reason(message.text, "варн")
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    count = await repo.add_warning(target.id, message.chat.id, reason, message.from_user.id)
    if count >= settings.MAX_WARNINGS:
        try:
            await message.chat.ban(target.id)
            await repo.clear_warnings(target.id, message.chat.id)
            await message.reply(f"🔨 {mention_user(target)} автобан за {count} варна!")
        except Exception as e:
            await message.reply(f"⚠️ {count}/{settings.MAX_WARNINGS} варнов: {e}")
    else:
        await message.reply(f"⚠️ {mention_user(target)} — варн <b>{count}/{settings.MAX_WARNINGS}</b>.\n📝 <i>{reason}</i>")


@router.message(F.text.regexp(CMD + r"разбан(\s|$)", flags=2))
@admin_only
async def cmd_unban(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        await message.reply(f"✅ {mention_user(target)} разбанен.")
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"вернуть(\s|$)", flags=2))
@admin_only
async def cmd_return(message: Message, **_):
    target = extract_target(message)
    if not target:
        await message.reply("ℹ️ Ответь на сообщение.")
        return
    try:
        await message.bot.unban_chat_member(message.chat.id, target.id, only_if_banned=True)
        link = await message.bot.create_chat_invite_link(message.chat.id, member_limit=1)
        try:
            await message.bot.send_message(target.id, f"✅ Тебя разбанили в <b>{message.chat.title}</b>!\nСсылка: {link.invite_link}")
            await message.reply(f"✅ {mention_user(target)} разбанен, ссылка отправлена.")
        except Exception:
            await message.reply(f"✅ Разбанен!\nСсылка: {link.invite_link}")
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(CMD + r"созвать\s+всех", flags=2))
@admin_only
async def cmd_summon(message: Message, **_):
    text = message.text or ""
    match = re.match(r"^[/!.]?созвать\s+всех\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    summon_msg = match.group(1).strip() if match else ""
    try:
        members = await message.bot.get_chat_administrators(message.chat.id)
        mentions = [mention_user(m.user) for m in members if not m.user.is_bot]
        out = "📢 <b>Созыв!</b>"
        if summon_msg:
            out += f"\n\n💬 {summon_msg}"
        if mentions:
            out += "\n\n" + " ".join(mentions)
        await message.reply(out)
    except Exception as e:
        await message.reply(f"❌ {e}")


@router.message(F.text.regexp(r"^\+правила", flags=2))
async def cmd_plus_rules(message: Message, is_admin: bool = False):
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    value = (message.text or "")[len("+правила"):].strip()
    if not value:
        await message.reply("ℹ️ Пример: +правила Не спамить")
        return
    await repo.update_chat_settings(message.chat.id, rules=value)
    await message.reply("✅ Правила обновлены!")


@router.message(F.text.regexp(r"^\+приветствие", flags=2))
async def cmd_plus_welcome(message: Message, is_admin: bool = False):
    if not is_admin:
        await message.reply("⛔ Только для администраторов!")
        return
    value = (message.text or "")[len("+приветствие"):].strip()
    if not value:
        await message.reply("ℹ️ Пример: +приветствие Привет!")
        return
    await repo.update_chat_settings(message.chat.id, welcome_message=value)
    await message.reply("✅ Приветствие обновлено!")


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_new_member(event: ChatMemberUpdated):
    user = event.new_chat_member.user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    # Проверяем базу нарушителей
    banned = await check_banlist_on_join(user.id, event.chat.id, event.bot)
    if banned:
        return
    cs = await repo.get_chat_settings(event.chat.id)
    welcome = cs.welcome_message or f"👋 Добро пожаловать, {mention_user(user)}!\nНапиши правила для ознакомления."
    try:
        await event.bot.send_message(event.chat.id, welcome)
    except Exception as e:
        logger.warning(f"Приветствие: {e}")


@router.message(F.text & ~F.text.startswith("/") & ~F.text.startswith("!") & ~F.text.startswith("+") & ~F.text.startswith("-") & ~F.text.startswith("."))
async def auto_filter(message: Message):
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
