"""
Магазин [ДК 9] и чатики (премиум валюта)
"""
from __future__ import annotations
import logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import repo

logger = logging.getLogger(__name__)
router = Router()

CHECKS_PACKAGES = [
    (15, 25, "Стартовый"),
    (50, 75, "Популярный 🔥"),
    (150, 200, "Премиум 💎"),
]


def shop_cmd(text: str) -> bool:
    t = text.lower().strip().lstrip("!/.")
    return t in ("магазин", "shop", "магаз")


@router.message(F.text.regexp(r"^[/!.]?(магазин|shop|магаз)$", flags=2))
async def cmd_shop(message: Message) -> None:
    items = await repo.get_shop_items()
    if not items:
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="➕ Добавить товар", callback_data="shop_add_help")
        ]])
        await message.reply(
            "🛒 <b>Магазин Chatix</b>\n\nПока товаров нет.\n\n"
            "<i>Используй /добавить_товар чтобы добавить товар</i>",
            reply_markup=kb
        )
        return
    lines = ["🛒 <b>Магазин Chatix</b>\n"]
    for item in items:
        price_str = f"🎫 {item.price_checks} чатиков" if item.price_checks > 0 else f"🍬 {item.price_iris} ирисок"
        premium = "💎 " if item.is_premium else ""
        lines.append(f"[{item.id}] {premium}<b>{item.name}</b> — {price_str}")
        if item.description:
            lines.append(f"    <i>{item.description}</i>")
    lines.append("\n<i>Купить: /купить [ID]</i>")
    await message.reply("\n".join(lines))


@router.callback_query(F.data == "shop_add_help")
async def cb_shop_add_help(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(
        "ℹ️ Чтобы добавить товар:\n\n"
        "<code>/добавить_товар Название|Описание|цена_ирис|цена_чатиков|0</code>\n\n"
        "Пример:\n<code>/добавить_товар VIP|Особая роль|0|50|1</code>"
    )


@router.message(F.text.regexp(r"^[/!.]?купить(\s|$)", flags=2))
async def cmd_buy(message: Message) -> None:
    text = message.text or ""
    import re
    text_clean = re.sub(r'^[/!.]', '', text).strip()
    parts = text_clean.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: /купить [ID товара]")
        return
    item_id = int(parts[1])
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    success, result = await repo.buy_item(user.id, item_id)
    if success:
        await message.reply(f"✅ Куплено: <b>{result}</b>! 🎉")
    else:
        await message.reply(f"❌ {result}")


@router.message(F.text.regexp(r"^[/!.]?чатики$", flags=2))
async def cmd_checks(message: Message) -> None:
    user = message.from_user
    checks = await repo.get_checks(user.id)
    await message.reply(
        f"🎫 Твои чатики: <b>{checks}</b>\n\n"
        f"Чатики — премиум валюта Chatix.\n"
        f"Купить: /купить_чатики"
    )


@router.message(F.text.regexp(r"^[/!.]?купить_чатики$", flags=2))
async def cmd_buy_checks(message: Message) -> None:
    lines = ["🎫 <b>Покупка чатиков за звёзды Telegram</b>\n"]
    kb = []
    for i, (checks, stars, label) in enumerate(CHECKS_PACKAGES, 1):
        lines.append(f"{i}. {label}: <b>{checks} чатиков</b> за ⭐ {stars} звёзд")
        kb.append([InlineKeyboardButton(text=f"{label}: {checks} чатиков за ⭐{stars}", callback_data=f"buy_checks:{i-1}")])
    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("buy_checks:"))
async def cb_buy_checks(call: CallbackQuery) -> None:
    idx = int(call.data.split(":")[1])
    checks, stars, label = CHECKS_PACKAGES[idx]
    await call.answer()
    await call.message.answer_invoice(
        title=f"Chatix — {checks} чатиков",
        description=f"Пакет «{label}»: {checks} чатиков",
        payload=f"checks:{checks}:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{checks} чатиков", amount=stars)],
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
        await message.reply(f"✅ Начислено <b>{checks} чатиков</b> 🎫\nБаланс: <b>{new_bal}</b>")


@router.message(Command("добавить_товар"))
async def cmd_add_item(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply(
            "ℹ️ Формат:\n<code>/добавить_товар Название|Описание|цена_ирис|цена_чатиков|0</code>\n\n"
            "Пример:\n<code>/добавить_товар VIP-статус|Особая роль|0|50|1</code>"
        )
        return
    try:
        name, desc, pi, pc, prem = parts[1].split("|")
        item = await repo.add_shop_item(name.strip(), desc.strip(), int(pi), int(pc), bool(int(prem)))
        await message.reply(f"✅ Товар добавлен! ID: <b>{item.id}</b>")
    except Exception:
        await message.reply("❌ Неверный формат. Пример:\n<code>/добавить_товар VIP|Роль|0|50|1</code>")
