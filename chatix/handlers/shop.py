"""
Магазин и премиум валюта (чеки)
/магазин, /купить, /чеки
Покупка чеков за звёзды Telegram
"""
from __future__ import annotations
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from database import repo

logger = logging.getLogger(__name__)
router = Router()

# Цены чеков в звёздах (1 звезда = ~0.013$)
CHECKS_PACKAGES = [
    (10, 50, "Стартовый"),
    (30, 130, "Популярный 🔥"),
    (100, 400, "Премиум"),
]


@router.message(Command("чеки"))
async def cmd_checks(message: Message) -> None:
    user = message.from_user
    checks = await repo.get_checks(user.id)
    await message.reply(
        f"🎫 Твои чеки: <b>{checks}</b>\n\n"
        f"Чеки — премиум валюта Chatix.\n"
        f"Используй их для покупки особых товаров в /магазин\n\n"
        f"<i>Купить чеки: /купить_чеки</i>"
    )


@router.message(Command("купить_чеки"))
async def cmd_buy_checks(message: Message) -> None:
    lines = ["🎫 <b>Покупка чеков за звёзды Telegram</b>\n"]
    kb = []
    for i, (checks, stars, label) in enumerate(CHECKS_PACKAGES, 1):
        lines.append(f"{i}. {label}: <b>{checks} чеков</b> за ⭐ {stars} звёзд")
        kb.append([InlineKeyboardButton(
            text=f"{label}: {checks} чеков за ⭐{stars}",
            callback_data=f"buy_checks:{i-1}"
        )])
    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("buy_checks:"))
async def cb_buy_checks(call: CallbackQuery) -> None:
    idx = int(call.data.split(":")[1])
    checks, stars, label = CHECKS_PACKAGES[idx]
    await call.answer()
    await call.message.answer_invoice(
        title=f"Chatix — {checks} чеков",
        description=f"Пакет «{label}»: {checks} чеков для покупок в магазине Chatix",
        payload=f"checks:{checks}:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{checks} чеков", amount=stars)],
    )


@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    if parts[0] == "checks" and len(parts) == 3:
        checks = int(parts[1])
        user_id = int(parts[2])
        new_bal = await repo.add_checks(user_id, checks)
        logger.info(f"[PAYMENT] {user_id} купил {checks} чеков")
        await message.reply(
            f"✅ Оплата прошла! Тебе начислено <b>{checks} чеков</b> 🎫\n"
            f"Текущий баланс: <b>{new_bal} чеков</b>"
        )


@router.message(Command("магазин"))
async def cmd_shop(message: Message) -> None:
    items = await repo.get_shop_items()
    if not items:
        await message.reply(
            "🛒 <b>Магазин Chatix</b>\n\n"
            "Пока товаров нет. Скоро появятся!\n\n"
            "<i>Администраторы могут добавить товары командой /добавить_товар</i>"
        )
        return

    lines = ["🛒 <b>Магазин Chatix</b>\n"]
    for item in items:
        price_str = ""
        if item.price_checks > 0:
            price_str = f"🎫 {item.price_checks} чеков"
        elif item.price_iris > 0:
            price_str = f"🍬 {item.price_iris} ирисок"
        premium = "💎 " if item.is_premium else ""
        lines.append(f"[{item.id}] {premium}<b>{item.name}</b> — {price_str}")
        if item.description:
            lines.append(f"    <i>{item.description}</i>")

    lines.append("\n<i>Купить: /купить [ID]</i>")
    await message.reply("\n".join(lines))


@router.message(Command("купить"))
async def cmd_buy(message: Message) -> None:
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: /купить [ID товара]")
        return

    item_id = int(parts[1])
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    success, result = await repo.buy_item(user.id, item_id)
    if success:
        await message.reply(f"✅ Ты купил: <b>{result}</b>! 🎉")
    else:
        await message.reply(f"❌ {result}")


@router.message(Command("добавить_товар"))
async def cmd_add_item(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return
    # /добавить_товар Название|Описание|цена_ирис|цена_чеков|premium(0/1)
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "ℹ️ Формат:\n<code>/добавить_товар Название|Описание|цена_ирис|цена_чеков|0</code>\n\n"
            "Пример:\n<code>/добавить_товар VIP-статус|Особая роль в чате|0|50|1</code>"
        )
        return
    try:
        name, desc, pi, pc, prem = parts[1].split("|")
        item = await repo.add_shop_item(name.strip(), desc.strip(), int(pi), int(pc), bool(int(prem)))
        await message.reply(f"✅ Товар добавлен! ID: <b>{item.id}</b>")
    except Exception:
        await message.reply("❌ Неверный формат.")
