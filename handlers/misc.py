"""Общие команды Chatix beta 1.10.5 — кнопочная помощь и ДК"""
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

# ══════════════════════════════════════════════════════════════════════════════
# ДАННЫЕ ДК
# ══════════════════════════════════════════════════════════════════════════════

DK_DATA = {
    1:  ("🛡️", "Модерация",        "бан, кик, мут [10m/2h/1d], анмут\nварн, разбан, вернуть\nсозвать всех [сообщение]"),
    2:  ("💰", "Экономика и игры", "баланс, бонус, перевод [сумма]\nказино [ставка] [red|black|green|even|odd|0-36]\nкости [ставка], ставка [сумма] [орёл|решка]"),
    3:  ("💑", "Браки",            "брак, развод, браки"),
    4:  ("⭐", "Репутация",        "+ или - в ответ на сообщение\nтоп — топ репутации/богачей/активных"),
    5:  ("🎭", "РП-команды",       "обнять, поцеловать, ударить\nпогладить, укусить, подмигнуть"),
    6:  ("👤", "Профиль",          "кто я, кто ты (ответ)\n+описание, +имя, +возраст\n+город, +страна, +хобби"),
    7:  ("⚙️", "Управление",       "кто админ, повысить, понизить\nпередать @юзернейм\n+правила, +приветствие"),
    8:  ("🚫", "Спамбаза",         "спам — просмотр\nспам+ [слово], спам- [слово]"),
    9:  ("🛒", "Магазин",          "магазин, купить [ID], инвентарь\nчатики, купить_чатики\nКнопки в магазине: ➕ товар | 💎 премиум"),
    10: ("📈", "Уровни и ачивки",  "уровень, ачивки, квесты\nXP за сообщения, стрики"),
    11: ("🏦", "Банк и работа",    "банк, вложить [сумма] [дни], снять [ID]\nработать (cooldown 4ч), ограбить (reply)"),
    12: ("🔨", "Аукцион",          "аукцион, создать_лот [название] [цена] [часы]\nставить [ID] [сумма]"),
    13: ("🏰", "Кланы",            "клан, кланы, создать_клан [название]\nвступить_клан [название], выйти_клан"),
    14: ("💚", "Дружба и подарки", "добавить_друга, принять_друга\nдрузья, запросы\nподарить [ID], инвентарь"),
    15: ("🚨", "Тикеты",           "жалоба [причина] (reply)\nтикеты, закрыть_тикет [ID]"),
    16: ("📊", "Аналитика",        "статистика\nмедленный [сек]\nлог [chat_id]"),
}

INSTALL_TEXT = """
📦 <b>Как добавить Chatix в свой чат</b>

<b>Шаг 1 — Добавь бота в группу</b>
Открой информацию о группе → Участники → Добавить участника → найди @chatixcm_bot

<b>Шаг 2 — Дай права администратора</b>
Нажми на бота → Назначить администратором
Включи:
• Удаление сообщений
• Бан пользователей
• Ограничение пользователей
• Изменение информации

<b>Шаг 3 — Готово!</b>
Напиши в чате <b>старт</b> — бот поприветствует всех 🎉

<i>За установку Chatix в чат ты получишь <b>+50 ирисок</b>! 🍬</i>
"""

PREMIUM_INFO_TEXT = """
💎 <b>Chatix Premium</b>

🎫 /фричатики — 1 бесплатный чатик каждый день
🛍️ Доступ к премиум-товарам в магазине (💎)
⚡ Приоритет в топе <i>(скоро)</i>
🎨 Цветной профиль с значком 💎 <i>(скоро)</i>
🎰 Двойные выигрыши по пятницам <i>(скоро)</i>

💰 Стоимость: <b>50 звёзд Telegram ⭐</b> / 30 дней
"""

CHECKS_PACKAGES = [
    (5,  10, "Мини"),
    (15, 25, "Стартовый"),
    (50, 75, "Популярный 🔥"),
]

# ══════════════════════════════════════════════════════════════════════════════
# КЛАВИАТУРЫ
# ══════════════════════════════════════════════════════════════════════════════

def kb_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Команды", callback_data="help_menu"),
            InlineKeyboardButton(text="🌲 ДК", callback_data="dk_menu"),
        ],
        [
            InlineKeyboardButton(text="📦 Установка", callback_data="show_install"),
            InlineKeyboardButton(text="💎 Премиум", callback_data="show_premium_info"),
        ],
    ])


def kb_help_menu() -> InlineKeyboardMarkup:
    """Главное меню помощи — категории ДК по 2 в ряд."""
    rows = []
    items = list(DK_DATA.items())
    for i in range(0, len(items), 2):
        row = []
        for dk_num, (emoji, name, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"{emoji} ДК {dk_num}",
                callback_data=f"dk_info:{dk_num}"
            ))
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text="🔑 ДК управление", callback_data="dk_control"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_dk_menu(chat_id: int | None = None) -> InlineKeyboardMarkup:
    """Меню управления ДК — список кнопок."""
    rows = []
    items = list(DK_DATA.items())
    for i in range(0, len(items), 2):
        row = []
        for dk_num, (emoji, name, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"{emoji} {dk_num}. {name}",
                callback_data=f"dk_toggle:{dk_num}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_dk_info(dk_num: int) -> InlineKeyboardMarkup:
    """Кнопки внутри страницы ДК."""
    prev_num = dk_num - 1 if dk_num > 1 else len(DK_DATA)
    next_num = dk_num + 1 if dk_num < len(DK_DATA) else 1
    prev_emoji = DK_DATA[prev_num][0]
    next_emoji = DK_DATA[next_num][0]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"◀️ {prev_emoji} ДК {prev_num}", callback_data=f"dk_info:{prev_num}"),
            InlineKeyboardButton(text=f"ДК {next_num} {next_emoji} ▶️", callback_data=f"dk_info:{next_num}"),
        ],
        [InlineKeyboardButton(text="⬅️ Все ДК", callback_data="help_menu")],
    ])


def kb_dk_toggle(dk_num: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Включить", callback_data=f"dk_enable:{dk_num}"),
            InlineKeyboardButton(text="❌ Выключить", callback_data=f"dk_disable:{dk_num}"),
        ],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="dk_menu")],
    ])


# ══════════════════════════════════════════════════════════════════════════════
# ХЭНДЛЕРЫ
# ══════════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text.lower().in_({"старт", "!старт", ".старт"}))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    if message.chat.type == "private":
        await message.answer(
            f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix beta 1.10.5</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
            f"Выбери раздел:",
            reply_markup=kb_main_menu()
        )
    else:
        await message.reply(
            f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix beta 1.10.5</b> — менеджер чатов.\n"
            f"Напиши <b>помощь</b> для списка команд.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="📋 Команды", callback_data="help_menu"),
                InlineKeyboardButton(text="🌲 ДК", callback_data="dk_menu"),
            ]])
        )


@router.message(Command("помощь", "help"))
@router.message(F.text.lower().in_({"помощь", "!помощь", ".помощь", "help", "!help", ".help"}))
async def cmd_help(message: Message) -> None:
    await message.reply(
        "🤖 <b>Chatix beta 1.10.5 | Помощь</b>\n\nВыбери раздел:",
        reply_markup=kb_help_menu()
    )


# ── Главное меню ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "🤖 <b>Chatix beta 1.10.5</b>\n\nВыбери раздел:",
        reply_markup=kb_main_menu()
    )


@router.callback_query(F.data == "help_menu")
async def cb_help_menu(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "📋 <b>Команды по разделам</b>\n\nВыбери ДК:",
        reply_markup=kb_help_menu()
    )


# ── Страница конкретного ДК ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("dk_info:"))
async def cb_dk_info(call: CallbackQuery) -> None:
    await call.answer()
    dk_num = int(call.data.split(":")[1])
    emoji, name, commands = DK_DATA[dk_num]
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\n"
        f"<code>{commands}</code>\n\n"
        f"<i>Команды работают с ! . / или без префикса</i>",
        reply_markup=kb_dk_info(dk_num)
    )


# ── ДК управление (список для вкл/выкл) ──────────────────────────────────────

@router.callback_query(F.data == "dk_menu")
async def cb_dk_menu(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "🌲 <b>Управление ДК</b>\n\nНажми на ДК чтобы включить/выключить:",
        reply_markup=kb_dk_menu()
    )


@router.callback_query(F.data.startswith("dk_toggle:"))
async def cb_dk_toggle(call: CallbackQuery) -> None:
    await call.answer()
    dk_num = int(call.data.split(":")[1])
    emoji, name, _ = DK_DATA[dk_num]
    tree = await repo.get_tree(call.message.chat.id, dk_num)
    status = "✅ включено" if tree.enabled else "❌ выключено"
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\n"
        f"Текущий статус: <b>{status}</b>\n\n"
        f"Что сделать?",
        reply_markup=kb_dk_toggle(dk_num)
    )


@router.callback_query(F.data.startswith("dk_enable:"))
async def cb_dk_enable(call: CallbackQuery) -> None:
    dk_num = int(call.data.split(":")[1])
    from handlers.roles import _get_effective_role
    role = await _get_effective_role(call.message)
    if role < 5:
        await call.answer("⛔ Только Владелец!", show_alert=True)
        return
    await repo.set_tree_enabled(call.message.chat.id, dk_num, True)
    emoji, name, _ = DK_DATA[dk_num]
    await call.answer(f"✅ ДК {dk_num} включено!", show_alert=True)
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\nСтатус: <b>✅ включено</b>",
        reply_markup=kb_dk_toggle(dk_num)
    )


@router.callback_query(F.data.startswith("dk_disable:"))
async def cb_dk_disable(call: CallbackQuery) -> None:
    dk_num = int(call.data.split(":")[1])
    from handlers.roles import _get_effective_role
    role = await _get_effective_role(call.message)
    if role < 5:
        await call.answer("⛔ Только Владелец!", show_alert=True)
        return
    await repo.set_tree_enabled(call.message.chat.id, dk_num, False)
    emoji, name, _ = DK_DATA[dk_num]
    await call.answer(f"❌ ДК {dk_num} выключено!", show_alert=True)
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\nСтатус: <b>❌ выключено</b>",
        reply_markup=kb_dk_toggle(dk_num)
    )


@router.callback_query(F.data == "dk_control")
async def cb_dk_control(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "🔑 <b>ДК управление (владелец)</b>\n\n"
        "<code>+дк N</code> — включить\n"
        "<code>-дк N</code> — выключить\n"
        "<code>!дк N M</code> — мин. должность\n"
        "<code>!дк</code> — список всех ДК",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌲 Управлять ДК кнопками", callback_data="dk_menu")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="help_menu")],
        ])
    )


# ── Правила ───────────────────────────────────────────────────────────────────

@router.message(Command("правила"))
@router.message(F.text.lower().in_({"правила", "!правила", ".правила"}))
async def cmd_rules(message: Message) -> None:
    cs = await repo.get_chat_settings(message.chat.id)
    rules = cs.rules or "📜 <b>Правила чата:</b>\n1. Уважайте друг друга\n2. Не спамьте\n3. Не рекламируйте"
    await message.reply(rules)


# ── Установка ─────────────────────────────────────────────────────────────────

@router.message(Command("установка"))
@router.message(F.text.lower().in_({"установка", "!установка", ".установка"}))
async def cmd_install(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await call.message.edit_text(
        INSTALL_TEXT + f"\n\n✅ <b>+50 ирисок начислено!</b> Баланс: <b>{new_bal} 🍬</b>",
        reply_markup=kb
    )


# ── Платно / Премиум ──────────────────────────────────────────────────────────

@router.message(Command("платно"))
@router.message(F.text.lower().in_({"платно", "!платно", ".платно"}))
async def cmd_paid(message: Message) -> None:
    lines = ["🎫 <b>Chatix — Платные функции</b>\n", "── Чатики ──"]
    kb = []
    for i, (checks, stars, label) in enumerate(CHECKS_PACKAGES):
        lines.append(f"• {label}: <b>{checks} 🎫</b> за ⭐ {stars}")
        kb.append([InlineKeyboardButton(
            text=f"{label}: {checks} 🎫 за ⭐{stars}",
            callback_data=f"buy_checks_paid:{i}"
        )])
    lines.append("\n── Премиум ──")
    lines.append("💎 <b>Premium</b> — 30 дней за ⭐ 50")
    kb.append([InlineKeyboardButton(text="ℹ️ О Premium", callback_data="show_premium_info")])
    kb.append([InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")])
    await message.reply("\n".join(lines), reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))


@router.callback_query(F.data == "show_premium_info")
async def cb_show_premium_info(call: CallbackQuery) -> None:
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await call.message.edit_text(PREMIUM_INFO_TEXT, reply_markup=kb)


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


@router.callback_query(F.data == "buy_premium")
async def cb_buy_premium(call: CallbackQuery) -> None:
    await call.answer()
    from aiogram.types import LabeledPrice
    await call.message.answer_invoice(
        title="Chatix Premium 💎",
        description="Премиум-подписка на 30 дней",
        payload=f"premium:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium 30 дней", amount=50)],
    )


# ── Фричатики ─────────────────────────────────────────────────────────────────

@router.message(Command("фричатики"))
@router.message(F.text.lower().in_({"фричатики", "!фричатики", ".фричатики"}))
async def cmd_free_chatik(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    ok, result = await repo.claim_free_chatik(user.id)
    if ok:
        await message.reply(
            f"🎫 {user.full_name}, ты получил <b>1 бесплатный чатик</b>!\n"
            f"Баланс: <b>{result} 🎫</b>\n\n<i>Следующий — через 24 часа</i>"
        )
    elif result == "no_premium":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")],
            [InlineKeyboardButton(text="ℹ️ Что даёт Premium?", callback_data="show_premium_info")],
        ])
        await message.reply(
            "💎 <b>Только для Premium-пользователей!</b>\n\nОформи подписку и получай 1 чатик в день 🎫",
            reply_markup=kb
        )
    elif result == "expired":
        await message.reply(
            "⌛ <b>Твой Premium истёк.</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💎 Продлить ⭐50", callback_data="buy_premium")
            ]])
        )
    else:
        await message.reply(f"⏳ Следующий бесплатный чатик через <b>{result}</b>.")


# ── Оплата Premium ────────────────────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment_misc(message: Message) -> None:
    payload = message.successful_payment.invoice_payload
    if payload.startswith("premium:"):
        user_id = int(payload.split(":")[1])
        await repo.activate_premium(user_id)
        await message.reply(
            "💎 <b>Premium активирован на 30 дней!</b>\n\n"
            "• /фричатики — 1 чатик каждый день\n"
            "• 💎 Премиум-товары в магазине\n\n"
            "Спасибо за поддержку Chatix! 🙏"
        )


# ── Приветствие ───────────────────────────────────────────────────────────────

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def on_new_member(event: ChatMemberUpdated) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    cs = await repo.get_chat_settings(event.chat.id)
    if cs and cs.welcome_message:
        text = cs.welcome_message.replace("{name}", f"<b>{user.full_name}</b>")
    else:
        text = (
            f"👋 Добро пожаловать, <b>{user.full_name}</b>!\n\n"
            f"Я <b>Chatix beta 1.10.5</b> — менеджер этого чата.\n"
            f"Напиши <b>помощь</b> чтобы узнать команды!"
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 Команды", callback_data="help_menu"),
        InlineKeyboardButton(text="🌲 ДК", callback_data="dk_menu"),
    ]])
    try:
        await event.answer(text, reply_markup=kb)
    except Exception as e:
        logger.warning(f"Приветствие: {e}")
