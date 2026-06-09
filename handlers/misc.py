"""Общие команды Chatix"""
from __future__ import annotations
import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from database import repo

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """
🤖 <b>Chatix | Чат-менеджер — Помощь</b>

<b>📋 Общие</b>
старт/помощь/правила/топ
кто я, кто ты (ответ), кто админ
бот — проверка работы бота

<b>🛡️ Модерация [ДК 1]</b>
бан, кик, мут [10m/2h/1d], анмут, варн
разбан, вернуть, созвать всех [сообщение]

<b>💰 Экономика и игры [ДК 2]</b>
баланс, бонус, перевод [сумма]
казино [ставка] [red|black|green|even|odd|0-36]
кости [ставка], ставка [сумма] [орёл|решка]

<b>💑 Браки [ДК 3]</b>
брак, развод, браки

<b>⭐ Репутация [ДК 4]</b>
+ или - в ответ на сообщение
топ — топ репутации/богачей/активных

<b>🎭 РП-команды [ДК 5]</b>
обнять, поцеловать, ударить, погладить, укусить, подмигнуть

<b>👤 Профиль [ДК 6]</b>
кто я, кто ты
+описание, +имя, +возраст, +город, +страна, +хобби

<b>⚙️ Управление [ДК 7]</b>
кто админ, повысить, понизить
передать @юзернейм
+правила, +приветствие

<b>🚫 Спамбаза [ДК 8]</b>
спам — просмотр
спам+ [слово], спам- [слово]

<b>🛒 Магазин [ДК 9]</b>
магазин, купить [ID]
чатики, купить_чатики
/добавить_товар (для админов)

<b>📊 Топ активности</b>
!топ, !топ вся, !топ [N]

<b>🔑 ДК управление (владелец)</b>
!дк — список ДК
+дк N / -дк N — вкл/выкл
!дк N M — мин. должность

<i>Команды работают с ! . / или без префикса</i>
"""


@router.message(CommandStart())
@router.message(Command("start"))
@router.message(F.text.lower().in_({"старт", "!старт", ".старт"}))
async def cmd_start(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await message.reply(
        f"🤖 Привет, <b>{user.full_name}</b>!\n\n"
        f"Я <b>Chatix</b> — менеджер чатов с экономикой, играми и модерацией.\n\n"
        f"Напиши помощь или /помощь для списка команд."
    )


@router.message(Command("помощь", "help"))
@router.message(F.text.lower().in_({"помощь", "!помощь", ".помощь", "help", "!help", ".help"}))
async def cmd_help(message: Message) -> None:
    await message.reply(HELP_TEXT)


@router.message(Command("правила"))
@router.message(F.text.lower().in_({"правила", "!правила", ".правила"}))
async def cmd_rules(message: Message) -> None:
    cs = await repo.get_chat_settings(message.chat.id)
    rules = cs.rules or "📜 <b>Правила чата:</b>\n1. Уважайте друг друга\n2. Не спамьте\n3. Не рекламируйте"
    await message.reply(rules)
