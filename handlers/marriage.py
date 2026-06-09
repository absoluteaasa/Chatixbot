"""
Модуль браков Chatix b1.7
/брак, /развод, /браки
"""
from __future__ import annotations
import asyncio, logging
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from config import settings
from database import repo
from utils.helpers import format_balance, mention_user

logger = logging.getLogger(__name__)
router = Router()

PROPOSAL_TIMEOUT = 60

# {(chat_id, target_id): (proposer_id, task)}
_pending_proposals: dict[tuple[int, int], tuple[int, asyncio.Task]] = {}


@router.message(Command("брак"))
@router.message(F.text.lower().in_({"брак", "!брак", ".брак", "/брак"}))
async def cmd_propose(message: Message) -> None:
    proposer = message.from_user
    await repo.get_or_create_user(proposer.id, proposer.username, proposer.full_name)

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "💍 Ответь на сообщение пользователя, которому хочешь сделать предложение!\n"
            "Пример: ответь на сообщение и напиши <b>брак</b>"
        )
        return

    target = message.reply_to_message.from_user
    if target.id == proposer.id:
        await message.reply("🤨 На себе жениться нельзя...")
        return
    if target.is_bot:
        await message.reply("🤖 Боты не вступают в браки!")
        return

    proposer_marriage = await repo.get_marriage(proposer.id, message.chat.id)
    if proposer_marriage:
        await message.reply("💔 Ты уже в браке! Сначала напиши <b>развод</b>.")
        return

    target_marriage = await repo.get_marriage(target.id, message.chat.id)
    if target_marriage:
        await message.reply(f"💔 {mention_user(target)} уже в браке!")
        return

    key = (message.chat.id, target.id)
    if key in _pending_proposals:
        await message.reply("⏳ Этому пользователю уже сделано предложение. Подожди ответа.")
        return

    db_proposer = await repo.get_user(proposer.id)
    if not db_proposer or db_proposer.balance < settings.MARRIAGE_COST:
        await message.reply(
            f"💸 Для заключения брака нужно {format_balance(settings.MARRIAGE_COST)}.\n"
            f"Твой баланс: {format_balance(db_proposer.balance if db_proposer else 0)}"
        )
        return

    async def _timeout():
        await asyncio.sleep(PROPOSAL_TIMEOUT)
        if key in _pending_proposals:
            del _pending_proposals[key]
            try:
                await message.answer(
                    f"⌛ Предложение {mention_user(proposer)} → {mention_user(target)} истекло."
                )
            except Exception:
                pass

    task = asyncio.create_task(_timeout())
    _pending_proposals[key] = (proposer.id, task)

    await message.reply(
        f"💍 {mention_user(proposer)} делает предложение {mention_user(target)}!\n\n"
        f"💌 {mention_user(target)}, ты согласен(а)?\n"
        f"Напиши <b>да</b> или <b>нет</b> в течение {PROPOSAL_TIMEOUT} секунд.\n"
        f"💰 Стоимость: {format_balance(settings.MARRIAGE_COST)}"
    )


@router.message(F.text.lower().in_({"да", "нет"}))
async def cmd_marriage_response(message: Message) -> None:
    user = message.from_user
    key = (message.chat.id, user.id)
    if key not in _pending_proposals:
        return

    proposer_id, task = _pending_proposals.pop(key)
    task.cancel()

    await repo.get_or_create_user(user.id, user.username, user.full_name)

    if (message.text or "").lower() == "нет":
        await message.reply(f"💔 {mention_user(user)} отказал(а)...")
        return

    proposer_db = await repo.get_user(proposer_id)
    if not proposer_db or proposer_db.balance < settings.MARRIAGE_COST:
        await message.reply("❌ У предложившего не хватает ирисок!")
        return

    await repo.update_balance(proposer_id, -settings.MARRIAGE_COST)
    await repo.create_marriage(proposer_id, user.id, message.chat.id)

    proposer_mention = f'<a href="tg://user?id={proposer_id}">{proposer_db.full_name or proposer_db.username or proposer_id}</a>'
    logger.info(f"[MARRIAGE] {proposer_id} + {user.id} в чате {message.chat.id}")
    await message.reply(
        f"💒 Поздравляем! {proposer_mention} и {mention_user(user)} теперь женаты! 💕\n"
        f"🎉 Желаем счастья и любви!"
    )


@router.message(Command("развод"))
@router.message(F.text.lower().in_({"развод", "!развод", ".развод", "/развод"}))
async def cmd_divorce(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    success = await repo.divorce(user.id, message.chat.id)
    if success:
        logger.info(f"[DIVORCE] {user.id} в чате {message.chat.id}")
        await message.reply(f"💔 {mention_user(user)} подал(а) на развод. Брак расторгнут.")
    else:
        await message.reply("💭 Ты не состоишь в браке.")


@router.message(Command("браки"))
@router.message(F.text.lower().in_({"браки", "!браки", ".браки", "/браки"}))
async def cmd_marriages_list(message: Message) -> None:
    marriages = await repo.get_all_marriages(message.chat.id)
    if not marriages:
        await message.reply("💭 В этом чате пока нет браков.")
        return
    lines = ["💑 <b>Браки чата:</b>\n"]
    for i, m in enumerate(marriages, 1):
        u1 = f'<a href="tg://user?id={m.user1_id}">{m.user1_id}</a>'
        u2 = f'<a href="tg://user?id={m.user2_id}">{m.user2_id}</a>'
        lines.append(f"{i}. {u1} 💕 {u2}")
    await message.reply("\n".join(lines))
