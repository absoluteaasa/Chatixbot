"""
ДК 9 — Магазин, инвентарь, чатики | Chatix 2.0
Кнопки: ➕ Добавить товар | 💎 Добавить премиум товар
"""
from __future__ import annotations
import logging
import re
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
)
from database import repo

logger = logging.getLogger(__name__)
router = Router()
CMD = r"^[/!.]?"

CHECKS_PACKAGES = [
    (15, 25, "Стартовый"),
    (50, 75, "Популярный 🔥"),
    (150, 200, "Премиум 💎"),
]


class AddItem(StatesGroup):
    waiting_name = State()
    waiting_desc = State()
    waiting_price = State()
    is_premium = State()


def shop_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Добавить товар", callback_data="shop_add:normal"),
            InlineKeyboardButton(text="💎 Добавить премиум", callback_data="shop_add:premium"),
        ]
    ])


@router.message(F.text.regexp(CMD + r"(магазин|shop|магаз)$", flags=re.IGNORECASE))
async def cmd_shop(message: Message) -> None:
    items = await repo.get_shop_items()
    normal = [i for i in items if not i.is_premium]
    premium = [i for i in items if i.is_premium]
    lines = ["🛒 <b>Магазин Chatix</b>\n"]
    if normal:
        lines.append("🔹 <b>Обычные товары</b>")
        for item in normal:
            price_str = f"🎫 {item.price_checks} чатиков" if item.price_checks > 0 else f"🍬 {item.price_iris} ирисок"
            lines.append(f"  [{item.id}] <b>{item.name}</b> — {price_str}")
            if item.description:
                lines.append(f"       <i>{item.description}</i>")
    if premium:
        lines.append("\n💎 <b>Премиум товары</b>")
        for item in premium:
            price_str = f"🎫 {item.price_checks} чатиков" if item.price_checks > 0 else f"🍬 {item.price_iris} ирисок"
            lines.append(f"  [{item.id}] 💎 <b>{item.name}</b> — {price_str}")
            if item.description:
                lines.append(f"       <i>{item.description}</i>")
    if not normal and not premium:
        lines.append("Пока товаров нет.")
    lines.append("\n<i>Купить: купить [ID]</i>")
    await message.reply("\n".join(lines), reply_markup=shop_keyboard())


# ── Кнопки добавления товара ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("shop_add:"))
async def cb_shop_add(call: CallbackQuery, state: FSMContext) -> None:
    is_premium = call.data.split(":")[1] == "premium"
    await state.set_state(AddItem.waiting_name)
    await state.update_data(is_premium=is_premium)
    await call.answer()
    label = "💎 ПРЕМИУМ" if is_premium else "обычного"
    await call.message.answer(
        f"➕ Создание <b>{label}</b> товара\n\n"
        f"Шаг 1/3: Напиши <b>название</b> товара"
    )


@router.message(AddItem.waiting_name)
async def add_item_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await state.set_state(AddItem.waiting_desc)
    await message.reply("Шаг 2/3: Напиши <b>описание</b> товара (или <code>-</code> чтобы пропустить)")


@router.message(AddItem.waiting_desc)
async def add_item_desc(message: Message, state: FSMContext) -> None:
    desc = "" if message.text.strip() == "-" else message.text.strip()
    await state.update_data(desc=desc)
    await state.set_state(AddItem.waiting_price)
    await message.reply(
        "Шаг 3/3: Напиши <b>цену</b>\n\n"
        "Форматы:\n"
        "<code>500</code> — в ирисках\n"
        "<code>чат 50</code> — в чатиках"
    )


@router.message(AddItem.waiting_price)
async def add_item_price(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip().lower()
    price_iris, price_checks = 0, 0
    try:
        if text.startswith("чат"):
            price_checks = int(text.split()[1])
        else:
            price_iris = int(text)
    except (ValueError, IndexError):
        await message.reply("❌ Неверный формат. Попробуй ещё раз: <code>500</code> или <code>чат 50</code>")
        return
    data = await state.get_data()
    item = await repo.add_shop_item(
        data["name"], data.get("desc", ""),
        price_iris, price_checks, data.get("is_premium", False)
    )
    label = "💎 Премиум товар" if item.is_premium else "Товар"
    await state.clear()
    await message.reply(
        f"✅ {label} <b>{item.name}</b> добавлен!\n"
        f"ID: <b>{item.id}</b>"
    )


# ── Покупка ───────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"купить(\s|$)", flags=re.IGNORECASE))
async def cmd_buy(message: Message) -> None:
    text = re.sub(r'^[/!.]', '', message.text or '').strip()
    parts = text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply("ℹ️ Использование: <code>купить [ID товара]</code>")
        return
    item_id = int(parts[1])
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    success, result = await repo.buy_item(user.id, item_id)
    if success:
        await repo.add_to_inventory(user.id, item_id)
        await message.reply(f"✅ Куплено: <b>{result}</b>! Товар добавлен в инвентарь 🎒")
    else:
        await message.reply(f"❌ {result}")


# ── Чатики ────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"чатики$", flags=re.IGNORECASE))
async def cmd_checks(message: Message) -> None:
    user = message.from_user
    checks = await repo.get_checks(user.id)
    await message.reply(
        f"🎫 Твои чатики: <b>{checks}</b>\n\n"
        f"Чатики — премиум валюта Chatix.\n"
        f"Купить: /купить_чатики"
    )


@router.message(F.text.regexp(CMD + r"купить_чатики$", flags=re.IGNORECASE))
async def cmd_buy_checks(message: Message) -> None:
    await message.reply("🎫 Для покупки чатиков и оформления Premium используй /платно")


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
