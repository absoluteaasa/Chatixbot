"""
ДК 11 — Банк, грабёж, работа | Chatix 2.0
"""
from __future__ import annotations
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import format_balance, mention_user

router = Router()
CMD = r"^[/!.]?"


@router.message(F.text.regexp(CMD + r"банк(\s|$)", flags=re.IGNORECASE))
async def cmd_bank(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    deposits = await repo.get_deposits(user.id)
    db_user = await repo.get_user(user.id)
    lines = [
        f"🏦 <b>Банк Chatix</b>\n",
        f"💰 На руках: {format_balance(db_user.balance if db_user else 0)}\n",
    ]
    if not deposits:
        lines.append("Активных вкладов нет.\n")
    else:
        lines.append("<b>Активные вклады:</b>")
        from datetime import datetime
        for d in deposits:
            ready = datetime.utcnow() >= d.withdraw_after
            status = "✅ Готов" if ready else f"⏳ до {d.withdraw_after.strftime('%d.%m %H:%M')}"
            profit = int(d.amount * d.rate / 100)
            lines.append(
                f"  [#{d.id}] {format_balance(d.amount)} под {d.rate}% → +{format_balance(profit)}\n"
                f"  {status}"
            )
    lines.append("\n<i>вложить [сумма] [дни] • снять [ID]</i>")
    await message.reply("\n".join(lines))


@router.message(F.text.regexp(CMD + r"вложить(\s|$)", flags=re.IGNORECASE))
async def cmd_deposit(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2:
        await message.reply(
            "ℹ️ Использование: <code>вложить [сумма] [дни]</code>\n\n"
            "Ставки:\n• 1-3 дня → 5%\n• 4-7 дней → 10%\n• 8+ дней → 15%"
        )
        return
    try:
        amount = int(parts[1])
        days = int(parts[2]) if len(parts) > 2 else 3
    except ValueError:
        await message.reply("❌ Неверный формат.")
        return
    if amount <= 0 or days <= 0:
        await message.reply("❌ Сумма и дни должны быть > 0")
        return
    ok, msg = await repo.deposit_bank(user.id, amount, days)
    if ok:
        await message.reply(f"✅ {mention_user(user)}, {msg}!\nВложено: {format_balance(amount)}")
    else:
        await message.reply(f"❌ {msg}")


@router.message(F.text.regexp(CMD + r"снять(\s|$)", flags=re.IGNORECASE))
async def cmd_withdraw(message: Message) -> None:
    user = message.from_user
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: <code>снять [ID вклада]</code>\nСписок: <code>банк</code>")
        return
    deposit_id = int(parts[1])
    ok, total = await repo.withdraw_deposit(user.id, deposit_id)
    if ok:
        await message.reply(f"✅ Вклад #{deposit_id} снят! Получено: {format_balance(total)}")
    else:
        from datetime import datetime
        deposits = await repo.get_deposits(user.id)
        dep = next((d for d in deposits if d.id == deposit_id), None)
        if dep:
            remaining = dep.withdraw_after - datetime.utcnow()
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            await message.reply(f"⏳ Вклад ещё не созрел. Подожди {h}ч {m}мин.")
        else:
            await message.reply("❌ Вклад не найден или уже снят.")


@router.message(F.text.regexp(CMD + r"работать(\s|$)", flags=re.IGNORECASE))
async def cmd_work(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    ok, earned, desc = await repo.do_work(user.id)
    if ok:
        await repo.progress_quest(user.id, message.chat.id, "transfer")
        await message.reply(
            f"💼 {desc}\n\n"
            f"💰 {mention_user(user)} заработал {format_balance(earned)}!"
        )
    else:
        await message.reply(f"⏳ Следующая работа через <b>{desc}</b>.")


@router.message(F.text.regexp(CMD + r"ограбить(\s|$)", flags=re.IGNORECASE))
async def cmd_rob(message: Message) -> None:
    user = message.from_user
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply("ℹ️ Ответь на сообщение жертвы и напиши <code>ограбить</code>")
        return
    target = message.reply_to_message.from_user
    if target.id == user.id:
        await message.reply("🤨 Сам себя не ограбишь.")
        return
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    ok, amount, msg = await repo.rob_user(user.id, target.id)
    if ok:
        await repo.award_achievement(user.id, "rob_success")
        await message.reply(
            f"🦹 {mention_user(user)} ограбил {mention_user(target)}!\n"
            f"Украдено: {format_balance(amount)} 🍬"
        )
    else:
        if msg == "провал":
            await message.reply(
                f"🚔 {mention_user(user)} провалил ограбление!\n"
                f"Штраф: {format_balance(amount)} 🍬"
            )
        else:
            await message.reply(f"❌ {msg}")
