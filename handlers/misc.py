"""Общие команды Chatix beta 1.10.6"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message, ChatMemberUpdated, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery, LabeledPrice
)
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION
from database import repo

logger = logging.getLogger(__name__)
router = Router()

# ══════════════════════════════════════════════════════════════════════════════
# ДАННЫЕ
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

ROLE_LABELS = {
    0: "0 — Все",
    1: "1 — Мл. модератор",
    2: "2 — Ст. модератор",
    3: "3 — Мл. админ",
    4: "4 — Ст. админ",
    5: "5 — Владелец",
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
Напиши в чате <b>старт</b> 🎉
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

def kb_main_menu(is_private: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="📋 Команды", callback_data="help_menu"),
            InlineKeyboardButton(text="🌲 ДК", callback_data="dk_menu"),
        ],
        [InlineKeyboardButton(text="💎 Премиум", callback_data="show_premium_info")],
    ]
    if is_private:
        rows.insert(1, [InlineKeyboardButton(text="📦 Установка (+50 🍬)", callback_data="show_install")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_help_menu() -> InlineKeyboardMarkup:
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
        InlineKeyboardButton(text="🔑 ДК управление", callback_data="dk_control_menu"),
        InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_dk_info(dk_num: int) -> InlineKeyboardMarkup:
    prev_num = dk_num - 1 if dk_num > 1 else len(DK_DATA)
    next_num = dk_num + 1 if dk_num < len(DK_DATA) else 1
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"◀️ ДК {prev_num}", callback_data=f"dk_info:{prev_num}"),
            InlineKeyboardButton(text=f"ДК {next_num} ▶️", callback_data=f"dk_info:{next_num}"),
        ],
        [InlineKeyboardButton(text="⬅️ Все ДК", callback_data="help_menu")],
    ])


def kb_dk_control_menu() -> InlineKeyboardMarkup:
    """Список всех ДК для управления."""
    rows = []
    items = list(DK_DATA.items())
    for i in range(0, len(items), 2):
        row = []
        for dk_num, (emoji, name, _) in items[i:i+2]:
            row.append(InlineKeyboardButton(
                text=f"{emoji} {dk_num}. {name}",
                callback_data=f"dk_manage:{dk_num}"
            ))
        rows.append(row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="help_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_dk_manage(dk_num: int, enabled: bool, min_role: int) -> InlineKeyboardMarkup:
    """Страница управления конкретным ДК: вкл/выкл + выбор минимальной роли."""
    toggle_btn = InlineKeyboardButton(
        text="❌ Выключить" if enabled else "✅ Включить",
        callback_data=f"dk_toggle:{dk_num}:{0 if enabled else 1}"
    )
    rows = [[toggle_btn]]
    # Кнопки ролей 0-5
    role_row = []
    for role_id, role_label in ROLE_LABELS.items():
        marker = "✅ " if role_id == min_role else ""
        role_row.append(InlineKeyboardButton(
            text=f"{marker}{role_label}",
            callback_data=f"dk_setrole:{dk_num}:{role_id}"
        ))
        if len(role_row) == 2:
            rows.append(role_row)
            role_row = []
    if role_row:
        rows.append(role_row)
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="dk_control_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ══════════════════════════════════════════════════════════════════════════════
# ХЭНДЛЕРЫ — СТАРТ И ПОМОЩЬ
# ══════════════════════════════════════════════════════════════════════════════

@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text.lower().in_({"старт", "!старт", ".старт"}))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    is_private = message.chat.type == "private"
    await message.answer(
        f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
        f"Я <b>Chatix beta 1.10.6</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
        f"Выбери раздел:",
        reply_markup=kb_main_menu(is_private=is_private)
    )


@router.message(Command("помощь", "help"))
@router.message(F.text.lower().in_({"помощь", "!помощь", ".помощь", "help", "!help", ".help"}))
async def cmd_help(message: Message) -> None:
    await message.reply(
        "🤖 <b>Chatix beta 1.10.6 | Помощь</b>\n\nВыбери раздел:",
        reply_markup=kb_help_menu()
    )


# ══════════════════════════════════════════════════════════════════════════════
# КОЛБЭКИ — НАВИГАЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery) -> None:
    await call.answer()
    is_private = call.message.chat.type == "private"
    await call.message.edit_text(
        "🤖 <b>Chatix beta 1.10.6</b>\n\nВыбери раздел:",
        reply_markup=kb_main_menu(is_private=is_private)
    )


@router.callback_query(F.data == "help_menu")
async def cb_help_menu(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "📋 <b>Команды по разделам</b>\n\nВыбери ДК:",
        reply_markup=kb_help_menu()
    )


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


# ══════════════════════════════════════════════════════════════════════════════
# КОЛБЭКИ — ДК УПРАВЛЕНИЕ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "dk_control_menu")
async def cb_dk_control_menu(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.edit_text(
        "🌲 <b>Управление ДК</b>\n\nВыбери ДК для настройки:",
        reply_markup=kb_dk_control_menu()
    )


@router.callback_query(F.data.startswith("dk_manage:"))
async def cb_dk_manage(call: CallbackQuery) -> None:
    await call.answer()
    dk_num = int(call.data.split(":")[1])
    emoji, name, _ = DK_DATA[dk_num]
    tree = await repo.get_tree(call.message.chat.id, dk_num)
    enabled = tree.enabled if tree else True
    min_role = tree.min_role if tree else 0
    status = "✅ включено" if enabled else "❌ выключено"
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Мин. звание: <b>{ROLE_LABELS[min_role]}</b>\n\n"
        f"Выбери действие или мин. звание для доступа:",
        reply_markup=kb_dk_manage(dk_num, enabled, min_role)
    )


@router.callback_query(F.data.startswith("dk_toggle:"))
async def cb_dk_toggle(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    dk_num, enable = int(parts[1]), bool(int(parts[2]))
    # Проверка прав — только владелец (роль 5)
    tree_owner = await repo.get_tree(call.message.chat.id, 7)
    from database.repo import ROLE_NAMES
    user_role = await _get_user_role(call.from_user.id, call.message.chat.id)
    if user_role < 5:
        await call.answer("⛔ Только Владелец может управлять ДК!", show_alert=True)
        return
    await repo.set_tree_enabled(call.message.chat.id, dk_num, enable)
    emoji, name, _ = DK_DATA[dk_num]
    status = "✅ включено" if enable else "❌ выключено"
    await call.answer(f"{'✅' if enable else '❌'} ДК {dk_num} {status}", show_alert=False)
    tree = await repo.get_tree(call.message.chat.id, dk_num)
    min_role = tree.min_role if tree else 0
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Мин. звание: <b>{ROLE_LABELS[min_role]}</b>\n\n"
        f"Выбери действие или мин. звание для доступа:",
        reply_markup=kb_dk_manage(dk_num, enable, min_role)
    )


@router.callback_query(F.data.startswith("dk_setrole:"))
async def cb_dk_setrole(call: CallbackQuery) -> None:
    parts = call.data.split(":")
    dk_num, new_role = int(parts[1]), int(parts[2])
    user_role = await _get_user_role(call.from_user.id, call.message.chat.id)
    if user_role < 5:
        await call.answer("⛔ Только Владелец может менять минимальное звание!", show_alert=True)
        return
    await repo.set_tree_min_role(call.message.chat.id, dk_num, new_role)
    emoji, name, _ = DK_DATA[dk_num]
    tree = await repo.get_tree(call.message.chat.id, dk_num)
    enabled = tree.enabled if tree else True
    status = "✅ включено" if enabled else "❌ выключено"
    await call.answer(f"✅ Мин. звание для ДК {dk_num}: {ROLE_LABELS[new_role]}", show_alert=False)
    await call.message.edit_text(
        f"{emoji} <b>ДК {dk_num} — {name}</b>\n\n"
        f"Статус: <b>{status}</b>\n"
        f"Мин. звание: <b>{ROLE_LABELS[new_role]}</b>\n\n"
        f"Выбери действие или мин. звание для доступа:",
        reply_markup=kb_dk_manage(dk_num, enabled, new_role)
    )


async def _get_user_role(user_id: int, chat_id: int) -> int:
    from database.db import async_session
    from database.db import UserRole
    from sqlalchemy import select, and_
    async with async_session() as s:
        result = await s.execute(select(UserRole).where(
            and_(UserRole.user_id == user_id, UserRole.chat_id == chat_id)
        ))
        rec = result.scalar_one_or_none()
        return rec.role if rec else 0


# ══════════════════════════════════════════════════════════════════════════════
# УСТАНОВКА — только в ЛС, бонус 1 раз
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("установка"))
@router.message(F.text.lower().in_({"установка", "!установка", ".установка"}))
async def cmd_install(message: Message) -> None:
    # Команда работает только в ЛС
    if message.chat.type != "private":
        await message.reply("📦 Инструкция по установке доступна только в личных сообщениях с ботом.")
        return
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    ok, new_bal = await repo.claim_install_bonus(user.id)
    bonus_text = f"\n\n🎁 <b>+50 ирисок за установку!</b> Баланс: <b>{new_bal} 🍬</b>" if ok else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить Премиум", callback_data="show_premium_info")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await message.reply(INSTALL_TEXT + bonus_text, reply_markup=kb)


@router.callback_query(F.data == "show_install")
async def cb_show_install(call: CallbackQuery) -> None:
    # Кнопка установки — только в ЛС
    if call.message.chat.type != "private":
        await call.answer("📦 Только в личных сообщениях!", show_alert=True)
        return
    await call.answer()
    user = call.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    ok, new_bal = await repo.claim_install_bonus(user.id)
    bonus_text = f"\n\n🎁 <b>+50 ирисок за установку!</b> Баланс: <b>{new_bal} 🍬</b>" if ok else ""
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Получить Премиум", callback_data="show_premium_info")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await call.message.edit_text(INSTALL_TEXT + bonus_text, reply_markup=kb)


# ══════════════════════════════════════════════════════════════════════════════
# ПРЕМИУМ
# ══════════════════════════════════════════════════════════════════════════════

@router.callback_query(F.data == "show_premium_info")
async def cb_show_premium_info(call: CallbackQuery) -> None:
    await call.answer()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")],
    ])
    await call.message.edit_text(PREMIUM_INFO_TEXT, reply_markup=kb)


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
    await call.message.answer_invoice(
        title="Chatix Premium 💎",
        description="Премиум-подписка на 30 дней",
        payload=f"premium:{call.from_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium 30 дней", amount=50)],
    )


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
        await message.reply(
            "💎 <b>Только для Premium!</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="💎 Купить Premium ⭐50", callback_data="buy_premium")
            ]])
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


# ══════════════════════════════════════════════════════════════════════════════
# ПРАВИЛА И ПРИВЕТСТВИЕ
# ══════════════════════════════════════════════════════════════════════════════

@router.message(Command("правила"))
@router.message(F.text.lower().in_({"правила", "!правила", ".правила"}))
async def cmd_rules(message: Message) -> None:
    cs = await repo.get_chat_settings(message.chat.id)
    rules = cs.rules or "📜 <b>Правила чата:</b>\n1. Уважайте друг друга\n2. Не спамьте\n3. Не рекламируйте"
    await message.reply(rules)


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
            f"Я <b>Chatix beta 1.10.6</b> — менеджер этого чата.\n"
            f"Напиши <b>помощь</b> чтобы узнать команды!"
        )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📋 Команды", callback_data="help_menu"),
        InlineKeyboardButton(text="🌲 ДК", callback_data="dk_manage_menu"),
    ]])
    try:
        await event.answer(text, reply_markup=kb)
    except Exception as e:
        logger.warning(f"Приветствие: {e}")
