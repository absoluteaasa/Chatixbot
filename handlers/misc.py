"""
Модуль общих команд: /старт, /помощь, /настройки (для админов).
"""

from __future__ import annotations

import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from database import repo

logger = logging.getLogger(__name__)
router = Router()

HELP_TEXT = """
🌸 <b>Chatix — Помощь</b>

<b>📋 Общие</b>
/старт — Начало работы
/помощь — Это сообщение
/профиль — Твоя статистика
/правила — Правила чата
/топ — Топ чата

<b>💰 Экономика</b>
/баланс — Твои ириски
/бонус — Ежедневная награда
/перевод [сумма] — Перевод (ответ на сообщение)

<b>🎰 Мини-игры</b>
/казино [ставка] [red|black|green|even|odd|0-36] — Рулетка
/кости [ставка] — Бросок кубиков
/ставка [сумма] [орёл|решка] — Монета

<b>💑 Браки</b>
/брак — Предложение (ответ на сообщение)
/развод — Расторгнуть брак
/браки — Список браков чата

<b>⭐ Репутация</b>
+ или - в ответ на сообщение — Изменить репутацию

<b>🎭 РП-команды</b>
!обнять, !поцеловать, !ударить, !погладить,
!укусить, !подмигнуть — (ответ на сообщение)

<b>🛡️ Модерация (только для админов)</b>
!бан [причина] — Забанить (ответ)
!кик [причина] — Кикнуть (ответ)
!мут [10m/2h/1d] [причина] — Замутить (ответ)
!анмут — Размутить (ответ)
!варн [причина] — Предупреждение (ответ)
"""


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    
    try:
        # Безопасная попытка зарегистрировать юзера
        await repo.get_or_create_user(user.id, user.username, user.full_name)
    except Exception as e:
        logger.error(f"Ошибка БД в cmd_start: {e}")
        await message.reply("⚠️ Ошибка: База данных недоступна или пуста. Проверьте логи Railway.")

    await message.reply(
        f"🌸 Привет, <b>{user.full_name}</b>!\n\n"
        f"Я <b>Chatix</b> — бот для управления чатом, развлечений и виртуальной экономики.\n\n"
        f"Напиши /помощь, чтобы увидеть все команды."
    )


@router.message(Command("помощь", "help"))
async def cmd_help(message: Message) -> None:
    # Команда помощи теперь вообще не трогает БД и обязана сработать!
    try:
        await message.reply(HELP_TEXT)
    except Exception as e:
        logger.error(f"Ошибка в cmd_help: {e}")


# ─── Настройки чата (для администраторов) ────────────────────────────────────

@router.message(Command("настройки"))
async def cmd_settings(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return

    try:
        chat_settings = await repo.get_chat_settings(message.chat.id)
        lines = [
            "⚙️ <b>Настройки чата</b>",
            "",
            f"🔗 Блокировка ссылок: {'✅' if chat_settings.block_links else '❌'}",
            f"🌊 Антифлуд: {'✅' if chat_settings.antiflood else '❌'}",
            f"🚫 Запрещённые слова: <code>{chat_settings.forbidden_words or 'нет'}</code>",
            "",
            "<i>Для изменения настроек свяжитесь с разработчиком или используйте команды:</i>",
            "/set_links — включить/выключить блокировку ссылок",
            "/add_word [слово] — добавить запрещённое слово",
            "/set_welcome [текст] — изменить приветствие",
            "/set_rules [текст] — изменить правила",
        ]
        await message.reply("\n".join(lines))
    except Exception as e:
        logger.error(f"Ошибка БД в cmd_settings: {e}")
        await message.reply("⚠️ Не удалось загрузить настройки чата из базы данных.")


@router.message(Command("set_links"))
async def cmd_toggle_links(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return
    try:
        chat_settings = await repo.get_chat_settings(message.chat.id)
        new_val = not chat_settings.block_links
        await repo.update_chat_settings(message.chat.id, block_links=new_val)
        state = "включена ✅" if new_val else "выключена ❌"
        await message.reply(f"🔗 Блокировка ссылок {state}")
    except Exception as e:
        logger.error(f"Ошибка БД в cmd_toggle_links: {e}")
        await message.reply("⚠️ Ошибка при изменении настроек в БД.")


@router.message(Command("add_word"))
async def cmd_add_forbidden_word(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("ℹ️ Использование: /add_word [слово]")
        return

    word = parts[1].strip().lower()
    try:
        chat_settings = await repo.get_chat_settings(message.chat.id)
        existing = set(chat_settings.forbidden_words.split("|")) if chat_settings.forbidden_words else set()
        existing.add(word)
        await repo.update_chat_settings(message.chat.id, forbidden_words="|".join(filter(None, existing)))
        await message.reply(f"✅ Слово <code>{word}</code> добавлено в чёрный список.")
    except Exception as e:
        logger.error(f"Ошибка БД в cmd_add_forbidden_word: {e}")
        await message.reply("⚠️ Ошибка при добавлении слова в БД.")


@router.message(Command("set_welcome"))
async def cmd_set_welcome(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("ℹ️ Использование: /set_welcome [текст приветствия]")
        return

    try:
        await repo.update_chat_settings(message.chat.id, welcome_message=parts[1])
        await message.reply("✅ Приветствие обновлено!")
    except Exception as e:
        logger.error(f"Ошибка БД in cmd_set_welcome: {e}")
        await message.reply("⚠️ Ошибка при сохранении приветствия.")


@router.message(Command("set_rules"))
async def cmd_set_rules(message: Message, is_admin: bool = False) -> None:
    if not is_admin:
        await message.reply("⛔ Только для администраторов.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply("ℹ️ Использование: /set_rules [текст правил]")
        return

    try:
        await repo.update_chat_settings(message.chat.id, rules=parts[1])
        await message.reply("✅ Правила обновлены!")
    except Exception as e:
        logger.error(f"Ошибка БД in cmd_set_rules: {e}")
        await message.reply("⚠️ Ошибка при сохранении правил.")
