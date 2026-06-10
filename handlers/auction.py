"""
ДК 12 — Аукцион | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import format_balance, mention_user

router = Router()
CMD = r"^[/!.]?"


@router.message(F.text.regexp(CMD + r"аукцион(\s|$)", flags=re.IGNORECASE))
async def cmd_auction_list(message: Message) -> None:
    auctions = await repo.get_active_auctions(message.chat.id)
    if not auctions:
        await message.reply(
            "🔨 <b>Аукцион</b>\n\nАктивных лотов нет.\n\n"
            "<i>Создать лот: <code>создать_лот [название] [цена] [часы]</code></i>"
        )
        return
    from datetime import datetime
    lines = ["🔨 <b>Активные лоты</b>\n"]
    for a in auctions:
        remaining = a.ends_at - datetime.utcnow()
        h = int(remaining.total_seconds() // 3600)
        m = int((remaining.total_seconds() % 3600) // 60)
        top = f"Топ: {format_balance(a.current_price)}" if a.top_bidder_id else f"Старт: {format_balance(a.start_price)}"
        lines.append(
            f"[#{a.id}] <b>{a.item_name}</b>\n"
            f"  {top} | ⏳ {h}ч {m}мин\n"
            f"  Ставка: <code>ставить {a.id} [сумма]</code>"
        )
    await message.reply("\n\n".join(lines) if len(lines) > 1 else lines[0])


@router.message(F.text.regexp(CMD + r"создать_лот(\s|$)", flags=re.IGNORECASE))
async def cmd_create_lot(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 3:
        await message.reply(
            "ℹ️ Использование:\n"
            "<code>создать_лот [название] [цена] [часы]</code>\n\n"
            "Пример: <code>создать_лот VIP-роль 500 2</code>"
        )
        return
    try:
        price = int(parts[-2])
        hours = int(parts[-1])
        name = " ".join(parts[1:-2])
    except (ValueError, IndexError):
        await message.reply("❌ Неверный формат.")
        return
    if price <= 0 or hours <= 0 or hours > 48:
        await message.reply("❌ Цена > 0, часы от 1 до 48.")
        return
    db_user = await repo.get_user(user.id)
    if not db_user or db_user.balance < price:
        await message.reply("❌ Недостаточно ирисок для залога.")
        return
    auction = await repo.create_auction(message.chat.id, user.id, name, price, hours)
    await message.reply(
        f"🔨 Лот <b>#{auction.id} {name}</b> выставлен!\n"
        f"Начальная цена: {format_balance(price)}\n"
        f"Длительность: {hours}ч\n\n"
        f"Ставки: <code>ставить {auction.id} [сумма]</code>"
    )


@router.message(F.text.regexp(CMD + r"ставить(\s|$)", flags=re.IGNORECASE))
async def cmd_bid(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.reply("ℹ️ Использование: <code>ставить [ID лота] [сумма]</code>")
        return
    auction_id, amount = int(parts[1]), int(parts[2])
    ok, msg = await repo.bid_auction(auction_id, user.id, amount)
    if ok:
        await repo.award_achievement(user.id, "auction_win")
        await message.reply(
            f"✅ {mention_user(user)} поставил {format_balance(amount)} на лот #{auction_id}!"
        )
    else:
        await message.reply(f"❌ {msg}")
