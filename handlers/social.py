"""
ДК 14 — Дружба, подарки, стена | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import mention_user

router = Router()
CMD = r"^[/!.]?"


@router.message(F.text.regexp(CMD + r"добавить_друга(\s|$)", flags=re.IGNORECASE))
async def cmd_add_friend(message: Message) -> None:
    user = message.from_user
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("ℹ️ Ответь на сообщение пользователя: <code>добавить_друга</code>")
        return
    target = message.reply_to_message.from_user
    if target.id == user.id:
        await message.reply("🤨 Нельзя добавить самого себя.")
        return
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    # Проверяем — может target уже нам отправил запрос
    pending = await repo.get_pending_requests(user.id)
    mutual = next((r for r in pending if r.from_id == target.id), None)
    if mutual:
        await repo.accept_friend(target.id, user.id)
        await message.reply(
            f"💚 {mention_user(user)} и {mention_user(target)} теперь друзья!"
        )
        return
    ok, msg = await repo.send_friend_request(user.id, target.id, message.chat.id)
    if ok:
        await message.reply(f"📨 {mention_user(user)} отправил запрос дружбы {mention_user(target)}!")
    else:
        await message.reply(f"❌ {msg}")


@router.message(F.text.regexp(CMD + r"принять_друга(\s|$)", flags=re.IGNORECASE))
async def cmd_accept_friend(message: Message) -> None:
    user = message.from_user
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("ℹ️ Ответь на сообщение пользователя: <code>принять_друга</code>")
        return
    requester = message.reply_to_message.from_user
    ok = await repo.accept_friend(requester.id, user.id)
    if ok:
        await message.reply(f"💚 {mention_user(user)} принял дружбу от {mention_user(requester)}!")
    else:
        await message.reply("❌ Запрос не найден.")


@router.message(F.text.regexp(CMD + r"друзья(\s|$)", flags=re.IGNORECASE))
async def cmd_friends(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    friend_ids = await repo.get_friends(target.id)
    if not friend_ids:
        await message.reply(f"😔 У {mention_user(target)} пока нет друзей.")
        return
    lines = [f"💚 <b>Друзья {mention_user(target)}</b>\n"]
    for fid in friend_ids:
        u = await repo.get_user(fid)
        name = (u.full_name or u.username or str(fid)) if u else str(fid)
        lines.append(f"• {name}")
    await message.reply("\n".join(lines))


@router.message(F.text.regexp(CMD + r"запросы(\s|$)", flags=re.IGNORECASE))
async def cmd_friend_requests(message: Message) -> None:
    user = message.from_user
    pending = await repo.get_pending_requests(user.id)
    if not pending:
        await message.reply("📭 Входящих запросов дружбы нет.")
        return
    lines = ["📨 <b>Запросы дружбы</b>\n"]
    for req in pending:
        u = await repo.get_user(req.from_id)
        name = (u.full_name or u.username or str(req.from_id)) if u else str(req.from_id)
        lines.append(f"• {name} — ответь на его сообщение и напиши <code>принять_друга</code>")
    await message.reply("\n".join(lines))


@router.message(F.text.regexp(CMD + r"подарить(\s|$)", flags=re.IGNORECASE))
async def cmd_gift(message: Message) -> None:
    user = message.from_user
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("ℹ️ Ответь на сообщение: <code>подарить [ID предмета]</code>")
        return
    target = message.reply_to_message.from_user
    if target.id == user.id:
        await message.reply("🤨 Себе дарить нельзя.")
        return
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: <code>подарить [ID предмета]</code>\nИнвентарь: <code>инвентарь</code>")
        return
    item_id = int(parts[1])
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    ok, msg = await repo.send_gift(user.id, target.id, item_id)
    if ok:
        item = await repo.get_shop_item(item_id)
        item_name = item.name if item else f"Предмет #{item_id}"
        await message.reply(f"🎁 {mention_user(user)} подарил <b>{item_name}</b> пользователю {mention_user(target)}!")
    else:
        await message.reply(f"❌ {msg}")


@router.message(F.text.regexp(CMD + r"инвентарь(\s|$)", flags=re.IGNORECASE))
async def cmd_inventory(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    inv = await repo.get_inventory(target.id)
    if not inv:
        await message.reply(f"🎒 Инвентарь {mention_user(target)} пуст.")
        return
    lines = [f"🎒 <b>Инвентарь {mention_user(target)}</b>\n"]
    for entry in inv:
        item = await repo.get_shop_item(entry.item_id)
        name = item.name if item else f"Предмет #{entry.item_id}"
        prem = "💎 " if item and item.is_premium else ""
        lines.append(f"• {prem}<b>{name}</b> x{entry.quantity} [ID: {entry.item_id}]")
    await message.reply("\n".join(lines))
