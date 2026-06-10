"""Общие команды Chatix"""
from __future__ import annotations
import logging
from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from database import repo

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """
🤖 <b>Chatix | Чат-менеджер — Помощь</b>

<b>📋 Общие</b>
/старт, /помощь, /правила, /топ
кто я, кто ты (ответ), кто админ

<b>🛡️ Модерация [ДК 1]</b>
!бан, !кик, !мут [10m/2h/1d], !анмут, !варн
!разбан, !вернуть

<b>💰 Экономика и игры [ДК 2]</b>
/баланс, /бонус, /перевод [сумма]
/казино [ставка] [red|black|green|even|odd|0-36]
/кости [ставка], /ставка [сумма] [орёл|решка]

<b>💑 Браки [ДК 3]</b>
/брак, /развод, /браки

<b>⭐ Репутация [ДК 4]</b>
+ или - в ответ на сообщение

<b>🎭 РП-команды [ДК 5]</b>
!обнять, !поцеловать, !ударить, !погладить, !укусить, !подмигнуть

<b>👤 Профиль [ДК 6]</b>
кто я, кто ты
+описание, +имя, +возраст, +город, +страна, +хобби

<b>⚙️ Управление [ДК 7]</b>
кто админ, !повысить, !понизить
/передать @юзернейм
!дк, +дк N, -дк N, !дк N M
+правила, +приветствие
!созвать всех [сообщение]

<b>🛒 Магазин</b>
/магазин — Список товаров
/купить [ID] — Купить товар
/чеки — Баланс чеков 🎫

<b>🚫 Спамбаза [ДК 7]</b>
!спам — Просмотр списка
!спам+ [слово] — Добавить
!спам- [слово] — Удалить

<i>Команды работают с ! . или без префикса</i>
"""


@router.message(CommandStart())
@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await message.reply(
        f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
        f"Я <b>Chatix</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
        f"Напиши /помощь для списка команд."
    )


@router.message(Command("помощь", "help"))
async def cmd_help(message: Message) -> None:
    await message.reply(HELP_TEXT)


@router.message(Command("правила"))
async def cmd_rules(message: Message) -> None:
    cs = await repo.get_chat_settings(message.chat.id)
    rules = cs.rules or "📜 <b>Правила чата:</b>\n1. Уважайте друг друга\n2. Не спамьте\n3. Не рекламируйте"
    await message.reply(rules)


@router.message(Command("настройки"))
async def cmd_settings(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return
    cs = await repo.get_chat_settings(message.chat.id)
    await message.reply(
        f"⚙️ <b>Настройки чата</b>\n\n"
        f"🔗 Блокировка ссылок: {'✅' if cs.block_links else '❌'}\n"
        f"🚫 Запрещённых слов: {len([w for w in cs.forbidden_words.split('|') if w])}"
    )
