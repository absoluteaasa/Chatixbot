"""
Модуль браков:
  /брак [ответ на сообщение] — предложение руки и сердца
  /развод — расторжение брака
  /браки — список браков чата
FSM: ожидание согласия второй стороны в течение 60 секунд.
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from config import settings
from database import repo
from utils.helpers import format_balance, mention_user

logger = logging.getLogger(__name__)
router = Router()

PROPOSAL_TIMEOUT = 60  # секунд


class MarriageStates(StatesGroup):
    waiting_for_consent = State()


# Хранит активные предложения: {(chat_id, target_id): proposer_id}
_pending_proposals: dict[tuple[int, int], int] = {}


# ─── Предложение брака ────────────────────────────────────────────────────────

@router.message(Command("брак"))
async def cmd_propose(message: Message) -> None:
    """
    /брак — ответ на сообщение пользователя, которому делаешь предложение.
    """
    proposer = message.from_user

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "💍 Ответь на сообщение пользователя, которому хочешь сделать предложение!\n"
            "Использование: <code>/брак</code> (в ответ на сообщение)"
        )
        return

    target = message.reply_to_message.from_user

    if target.id == proposer.id:
        await message.reply("🤨 На себе жениться нельзя...")
        return

    if target.is_bot:
        await message.reply("🤖 Боты не вступают в браки!")
        return

    # Проверяем существующие браки
    proposer_marriage = await repo.get_marriage(proposer.id, message.chat.id)
    if proposer_marriage:
        await message.reply(f"💔 Ты уже в браке! Сначала напиши /развод.")
        return

    target_marriage = await repo.get_marriage(target.id, message.chat.id)
    if target_marriage:
        await message.reply(f"💔 {mention_user(target)} уже в браке!")
        return

    # Проверяем, нет ли дублирующего предложения
    key = (message.chat.id, target.id)
    if key in _pending_proposals:
        await message.reply("⏳ Этому пользователю уже сделано предложение. Подожди ответа.")
        return

    # Проверяем баланс
    await repo.get_or_create_user(proposer.id, proposer.username, proposer.full_name)
    db_proposer = await repo.get_user(proposer.id)
    if not db_proposer or db_proposer.balance < settings.MARRIAGE_COST:
        await message.reply(
            f"💸 Для заключения брака нужно {format_balance(settings.MARRIAGE_COST)}.\n"
            f"Твой баланс: {format_balance(db_proposer.balance if db_proposer else 0)}"
        )
        return

    _pending_proposals[key] = proposer.id

    await message.reply(
        f"💍 {mention_user(proposer)} делает предложение {mention_user(target)}!\n\n"
        f"💌 {mention_user(target)}, ты согласен(а)? Напиши <b>да</b> или <b>нет</b> в течение {PROPOSAL_TIMEOUT} секунд.\n"
        f"💰 Стоимость: {format_balance(settings.MARRIAGE_COST)}"
    )

    # Автоотмена через таймаут
    await asyncio.sleep(PROPOSAL_TIMEOUT)
    if key in _pending_proposals:
        del _pending_proposals[key]
        try:
            await message.answer(
                f"⌛ Предложение {mention_user(proposer)} к {mention_user(target)} истекло."
            )
        except Exception:
            pass


# ─── Ответ на предложение ─────────────────────────────────────────────────────

@router.message(F.text.lower().in_({"да", "нет"}))
async def cmd_marriage_response(message: Message) -> None:
    user = message.from_user
    chat_id = message.chat.id

    key = (chat_id, user.id)
    if key not in _pending_proposals:
        return  # Не ждём ответа от этого пользователя

    proposer_id = _pending_proposals.pop(key)
    proposer = await repo.get_user(proposer_id)

    if not proposer:
        await message.reply("❌ Предложивший пользователь не найден.")
        return

    if (message.text or "").lower() == "нет":
        await message.reply(
            f"💔 {mention_user(user)} отказал(а)..."
        )
        return

    # Согласие — оформляем брак
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    # Списываем ириски с предложившего
    success = await repo.update_balance(proposer_id, -settings.MARRIAGE_COST)

    # Имитируем mention через фиктивный объект
    class _FakeUser:
        def __init__(self, u):
            self.id = u.id
            self.full_name = u.full_name
            self.username = u.username

    proposer_mention = f'<a href="tg://user?id={proposer_id}">{proposer.full_name or proposer.username or proposer_id}</a>'

    marriage = await repo.create_marriage(proposer_id, user.id, chat_id)

    logger.info(f"[MARRIAGE] {proposer_id} + {user.id} в чате {chat_id}")
    await message.reply(
        f"💒 Поздравляем! {proposer_mention} и {mention_user(user)} теперь женаты! 💕\n\n"
        f"🎉 Желаем счастья и любви!"
    )


# ─── Развод ───────────────────────────────────────────────────────────────────

@router.message(Command("развод"))
async def cmd_divorce(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    success = await repo.divorce(user.id, message.chat.id)

    if success:
        logger.info(f"[DIVORCE] {user.id} в чате {message.chat.id}")
        await message.reply(
            f"💔 {mention_user(user)} подал(а) на развод...\n"
            f"Брак расторгнут. Мы скорбим."
        )
    else:
        await message.reply(f"🤷 {mention_user(user)}, ты не в браке в этом чате.")


# ─── Список браков ────────────────────────────────────────────────────────────

@router.message(Command("браки"))
async def cmd_marriages_list(message: Message) -> None:
    marriages = await repo.get_all_marriages(message.chat.id)

    if not marriages:
        await message.reply("💔 В этом чате пока нет браков. Будь первым!")
        return

    lines = ["💒 <b>Браки чата:</b>\n"]
    for i, m in enumerate(marriages, 1):
        u1 = await repo.get_user(m.user1_id)
        u2 = await repo.get_user(m.user2_id)
        name1 = u1.full_name or u1.username if u1 else str(m.user1_id)
        name2 = u2.full_name or u2.username if u2 else str(m.user2_id)
        date = m.created_at.strftime("%d.%m.%Y")
        lines.append(f"{i}. 💕 {name1} & {name2} <i>(с {date})</i>")

    await message.reply("\n".join(lines))
