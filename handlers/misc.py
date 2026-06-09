"""Общие команды Chatix 1.8"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ChatMemberUpdated, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from database import repo

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """
🤖 <b>Chatix 1.8 | Помощь</b>

<b>📋 Общие</b>
старт/помощь/правила/топ
кто я, кто ты (ответ), кто админ
бот — проверка работы

<b>🛡️ Модерация [ДК 1]</b>
бан, кик, мут [10m/2h/1d], анмут, варн
разбан, вернуть, созвать всех

<b>💰 Экономика и игры [ДК 2]</b>
баланс, бонус, перевод [сумма]
казино [ставка], кости [ставка], ставка [сумма]

<b>💑 Браки [ДК 3]</b>
брак, развод, браки

<b>⭐ Репутация [ДК 4]</b>
+ или - в ответ, топ

<b>🎭 РП-команды [ДК 5]</b>
!обнять, !поцеловать, !ударить, !погладить, !укусить, !подмигнуть

<b>👤 Профиль [ДК 6]</b>
кто я, кто ты, +описание, +имя, +возраст, +город, +страна, +хобби

<b>⚙️ Управление [ДК 7]</b>
кто админ, повысить, понизить, передать @юзернейм
+правила, +приветствие

<b>🚫 Спамбаза [ДК 8]</b>
спам, спам+ [слово], спам- [слово]

<b>🛒 Магазин [ДК 9]</b>
магазин, купить [ID]
/платно — чатики и премиум
/фричатики — бесплатный чатик (только для 💎 премиум)

<b>✨ Новое в 1.8</b>
+название, +описание_чата, закреп, открепить
очистить [N], кик неактив [дни]
дуэль [ставка] — вызов на дуэль
+заметка, -заметка, ~заметка, #заметка, заметки

<b>📊 Топ активности</b>
!топ, !топ вся, !топ [N]

<b>🔑 ДК управление (владелец)</b>
!дк — список, +дк N / -дк N — вкл/выкл

<i>Команды работают с ! . / или без префикса</i>
"""

INSTALL_TEXT = """
📦 <b>Как добавить Chatix в свой чат</b>

<b>Шаг 1 — Добавь бота в группу</b>
Открой информацию о группе → Участники → Добавить участника → найди @ChatixBot

<b>Шаг 2 — Дай права администратора</b>
Нажми на бота в списке → Назначить администратором
Включи права:
• Удаление сообщений
• Бан пользователей
• Ограничение пользователей
• Изменение информации

<b>Шаг 3 — Готово!</b>
Напиши в чате <b>старт</b> — бот поприветствует всех 🎉

<b>Полезные команды после установки:</b>
• <b>+правила</b> [текст] — задать правила чата
• <b>+приветствие</b> [текст] — задать приветствие
• <b>помощь</b> — полный список команд

<i>За установку Chatix в чат ты получишь <b>+50 ирисок</b>! 🍬</i>
"""

PREMIUM_INFO_TEXT = """
💎 <b>Chatix Premium — что открывает подписка</b>

🎫 <b>/фричатики</b> — 1 бесплатный чатик каждый день
🛍️ <b>Доступ к премиум-товарам</b> в магазине (помечены 💎)
⚡ <b>Приоритет</b> в топе и повышенный множитель репутации <i>(скоро)</i>
🎨 <b>Цветной профиль</b> с премиум-значком 💎 <i>(скоро)</i>
🎰 <b>Двойные выигрыши</b> в казино по пятницам <i>(скоро)</i>
🔔 <b>Уведомления об активности чата</b> в личку <i>(скоро)</i>

💰 Стоимость: <b>50 звёзд Telegram ⭐</b> на 30 дней

<i>Нажми кнопку ниже чтобы оформить подписку!</i>
"""


@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text.lower().in_({"старт", "!старт", ".старт"}))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    # В личке — полное приветствие с кнопками
    if message.chat.type == "private":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Список команд", callback_data="show_help")],
            [InlineKeyboardButton(text="📦 Как установить бота в чат", callback_data="show_install")],
            [InlineKeyboardButton(text="💎 Премиум", callback_data="show_premium_info")],
        ])
        await message.answer(
            f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix 1.8</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
            f"Напиши /помощь для списка команд или /установка для инструкции.",
            reply_markup=kb
        )
    else:
        await message.reply(
            f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix 1.8</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
            f"Напиши /помощь для списка команд."
        )


@router.message(Command("помощь", "help"))
@router.message(F.text.lower().in_({"помощь", "!помощь", ".помощь", "help", "!help", ".help"}))
async def cmd_help(message: Message) -> None:
    await message.reply(HELP_TEXT)


@router.callback_query(F.data == "show_help")
async def cb_show_help(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer(HELP_TEXT)


@router.message(Command("правила"))
@router.message(F.text.lower().in_({"правила", "!правила", ".правила"}))
async def cmd_rules(message: Message) -> None:
    cs = await repo.get_chat_settings(message.chat.id)
    rules = cs.rules or "📜 <b>Правила чата:</b>\n1. Уважайте друг друга\n2. Не спамьте\n3. Не рекламируйте"
    await message.reply(rules)


# ─── /установка ───────────────────────────────────────────────────────────────

@router.message(Command("установка"))
@router.message(F.text.lower().in_({"установка", "!установка", ".установка"}))
async def cmd_install(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    # Начисляем 50 ирисок за просмотр инструкции
    new_bal = await repo.update_balance(user.id, 50)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить Премиум", callback_data="show_premium_info")],
    ])
    await message.reply(
        INSTALL_TEXT + f"\n\n✅ <b>+50 ирисок начислено!</b> Баланс: <b>{new_bal} 🍬</b>",
        reply_markup=kb
    )


@router.callback_query(F.data == "show_install")
async def cb_show_install(call: CallbackQuery) -> None:
    await call.answer()
    user = call.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    new_bal = await repo.update_balance(user.id, 50)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить Премиум", callback_data="show_premium_info")],
    ])
    await call.message.answer(
        INSTALL_TEXT + f"\n\n✅ <b>+50 ирисок начислено!</b> Баланс: <b>{new_bal} 🍬</b>",
        reply_markup=kb
    )


# ─── /платно — покупка чатиков и премиума ─────────────────────────────────────

CHECKS_PACKAGES = [
    (5, 10, "Мини"),
    (15, 25, "Стартовый"),
    (50, 75, "Популярный 🔥"),
]

@router.message(Command("платно"))
@router.message(F.text.lower().in_({"платно", "!платно", ".платно"}))
async def cmd_paid(message: Message) -> None:
    lines = ["🎫 <b>Chatix — Платные функции</b>\n"]
    lines.append("── Чатики (премиум-валюта) ──")
    kb = []
    for checks, stars, label in CHECKS_PACKAGES:
        lines.append(f"• {label}: <b>{checks} чатиков</b> за ⭐ {stars} звёзд")
        kb.append([InlineKeyboardButton(
            text=f"{label}: {checks} 🎫 за ⭐{stars}",
            callback_data=f"buy_checks_paid:{CHECKS_PACKAGES.index((checks, stars, label))}"
        )])
    lines.append("\n── Премиум-подписка ──")
    lines.append("💎 <b>Premium</b> — 30 дней за ⭐ 50 звёзд")
    lines.append("<i>Открывает /фричатики и премиум-товары</i>")
    kb.append([InlineKeyboardButton(text="💎 Узнать о Premium", callback_data="show_premium_info")])
    kb.append([InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")])
    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data.startswith("buy_checks_paid:"))
async def cb_buy_checks_paid(call: CallbackQuery) -> None:
    idx = int(call.data.split(":")[1])
    checks, stars, label = CHECKS_PACKAGES[idx]
    await call.answer()
    await call.message.answer_invoice(
        title=f"Chatix — {checks} чатиков",
        description=f"Пакет «{label}»: {checks} чатиков",
        payload=f"checks:{checks}:{call.from_user.id}",
        currency="XTR",
        prices=[{"label": f"{checks} чатиков", "amount": stars}],
    )


@router.callback_query(F.data == "show_premium_info")
async def cb_show_premium_info(call: CallbackQuery) -> None:
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Premium за ⭐50", callback_data="buy_premium")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_paid")],
    ])
    await call.message.answer(PREMIUM_INFO_TEXT, reply_markup=kb)


@router.callback_query(F.data == "back_to_paid")
async def cb_back_to_paid(call: CallbackQuery) -> None:
    await call.answer()
    # Переиспользуем логику cmd_paid через фейковый message
    lines = ["🎫 <b>Chatix — Платные функции</b>\n"]
    lines.append("── Чатики (премиум-валюта) ──")
    kb = []
    for checks, stars, label in CHECKS_PACKAGES:
        lines.append(f"• {label}: <b>{checks} чатиков</b> за ⭐ {stars} звёзд")
        kb.append([InlineKeyboardButton(
            text=f"{label}: {checks} 🎫 за ⭐{stars}",
            callback_data=f"buy_checks_paid:{CHECKS_PACKAGES.index((checks, stars, label))}"
        )])
    lines.append("\n── Премиум-подписка ──")
    lines.append("💎 <b>Premium</b> — 30 дней за ⭐ 50 звёзд")
    kb.append([InlineKeyboardButton(text="💎 Узнать о Premium", callback_data="show_premium_info")])
    kb.append([InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")])
    await call.message.answer("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "buy_premium")
async def cb_buy_premium(call: CallbackQuery) -> None:
    await call.answer()
    from aiogram.types import LabeledPrice
    await call.message.answer_invoice(
        title="Chatix Premium 💎",
        description="Премиум-подписка на 30 дней: /фричатики, доступ к премиум-товарам и многое другое!",
        payload=f"premium:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium 30 дней", amount=50)],
    )


# ─── /фричатики — бесплатный чатик для премиум ────────────────────────────────

@router.message(Command("фричатики"))
@router.message(F.text.lower().in_({"фричатики", "!фричатики", ".фричатики"}))
async def cmd_free_chatik(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    ok, result = await repo.claim_free_chatik(user.id)
    if ok:
        await message.reply(
            f"🎫 {user.full_name}, ты получил <b>1 бесплатный чатик</b>!\n"
            f"Баланс чатиков: <b>{result} 🎫</b>\n\n"
            f"<i>Следующий бесплатный чатик — через 24 часа</i>"
        )
    elif result == "no_premium":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")],
            [InlineKeyboardButton(text="ℹ️ Что даёт Premium?", callback_data="show_premium_info")],
        ])
        await message.reply(
            "💎 <b>Эта команда только для Premium-пользователей!</b>\n\n"
            "Оформи подписку и получай 1 бесплатный чатик каждый день 🎫",
            reply_markup=kb
        )
    elif result == "expired":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Продлить Premium ⭐50", callback_data="buy_premium")],
        ])
        await message.reply(
            "⌛ <b>Твой Premium истёк.</b>\n\nПродли подписку чтобы снова получать бесплатные чатики!",
            reply_markup=kb
        )
    else:
        await message.reply(
            f"⏳ Следующий бесплатный чатик через <b>{result}</b>."
        )


# ─── Обработка оплаты Premium ─────────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment_misc(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    if payload.startswith("premium:"):
        user_id = int(payload.split(":")[1])
        await repo.activate_premium(user_id)
        await message.reply(
            "💎 <b>Premium активирован на 30 дней!</b>\n\n"
            "Теперь тебе доступно:\n"
            "• /фричатики — 1 чатик каждый день\n"
            "• 💎 Премиум-товары в магазине\n\n"
            "Спасибо за поддержку Chatix! 🙏"
        )


# ─── Приветствие новых участников ─────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_new_member(event: ChatMemberUpdated) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    cs = await repo.get_chat_settings(event.chat.id)
    if cs and cs.welcome_message:
        # Используем кастомное приветствие из настроек чата
        text = cs.welcome_message.replace("{name}", f"<b>{user.full_name}</b>")
    else:
        text = (
            f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix 1.8</b> — менеджер этого чата.\n"
            f"Напиши /помощь чтобы узнать мои команды, и /установка чтобы добавить меня в свой чат!"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Команды", callback_data="show_help")],
        [InlineKeyboardButton(text="📦 Установить в свой чат", callback_data="show_install")],
    ])
    await event.answer(text, reply_markup=kb)
