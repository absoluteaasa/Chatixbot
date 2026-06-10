"""
Модуль репутации и статистики Chatix 1.8.
Команды работают с !, /, . или без префикса.
"""

from __future__ import annotations
import logging
import re
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import format_balance, mention_user

logger = logging.getLogger(__name__)
router = Router()

CMD = r"^[/!.]?"

# ─── Голосование репутации ────────────────────────────────────────────────────

@router.message(F.reply_to_message & F.text.regexp(r"^\s*[+\-]\s*$"))
async def cmd_reputation_vote(message: Message) -> None:
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return
    voter = message.from_user
    target = message.reply_to_message.from_user
    text = (message.text or "").strip()
    if voter.id == target.id:
        await message.reply("🙄 Нельзя голосовать за самого себя!")
        return
    if target.is_bot:
        await message.reply("🤖 Ботам репутация не нужна.")
        return
    value = 1 if text == "+" else -1
    await repo.get_or_create_user(voter.id, voter.username, voter.full_name)
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    success, error_msg = await repo.vote_reputation(voter.id, target.id, message.chat.id, value)
    if not success:
        await message.reply(f"⏳ {error_msg}")
        return
    direction = "повышена ⬆️" if value == 1 else "понижена ⬇️"
    db_target = await repo.get_user(target.id)
    new_rep = db_target.reputation if db_target else 0
    logger.info(f"[REP] {voter.id} → {target.id}: {value:+d}, новая репутация: {new_rep}")
    await message.reply(
        f"{'⭐' if value == 1 else '💀'} Репутация {mention_user(target)} {direction}!\n"
        f"Текущая репутация: <b>{new_rep:+d}</b>"
    )


# ─── профиль ──────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"профиль(\s|$)", flags=re.IGNORECASE))
async def cmd_profile(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = message.from_user
    await repo.get_or_create_user(target.id, target.username, target.full_name)
    db_user = await repo.get_user(target.id)
    if not db_user:
        await message.reply("❌ Пользователь не найден.")
        return
    marriage = await repo.get_marriage(target.id, message.chat.id)
    marriage_info = "Нет 💔"
    if marriage:
        partner_id = marriage.user2_id if marriage.user1_id == target.id else marriage.user1_id
        partner = await repo.get_user(partner_id)
        if partner:
            partner_name = partner.full_name or partner.username or str(partner_id)
            marriage_info = f"💍 {partner_name}"
    lines = [
        f"👤 <b>Профиль {mention_user(target)}</b>",
        f"",
        f"💰 Баланс: {format_balance(db_user.balance)}",
        f"⭐ Репутация: <b>{db_user.reputation:+d}</b>",
        f"💬 Сообщений: <b>{db_user.messages_count:,}</b>",
        f"⚠️ Предупреждений: <b>{db_user.warnings}</b>",
        f"💑 Брак: {marriage_info}",
        f"📅 В боте с: <b>{db_user.created_at.strftime('%d.%m.%Y')}</b>",
    ]
    await message.reply("\n".join(lines))


# ─── топ ──────────────────────────────────────────────────────────────────────

@router.message(F.text.regexp(CMD + r"топ(\s|$)", flags=re.IGNORECASE))
async def cmd_top(message: Message) -> None:
    top = await repo.get_top_users(limit=10)
    sections = []
    medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7

    rich_lines = ["🏆 <b>Топ богачей</b>"]
    for i, u in enumerate(top["rich"]):
        rich_lines.append(f"{medals[i]} {u.full_name or u.username or u.id} — {format_balance(u.balance)}")
    sections.append("\n".join(rich_lines))

    active_lines = ["💬 <b>Топ активных</b>"]
    for i, u in enumerate(top["active"]):
        active_lines.append(f"{medals[i]} {u.full_name or u.username or u.id} — {u.messages_count:,} сообщ.")
    sections.append("\n".join(active_lines))

    rep_lines = ["⭐ <b>Топ репутации</b>"]
    for i, u in enumerate(top["reputable"]):
        rep_lines.append(f"{medals[i]} {u.full_name or u.username or u.id} — {u.reputation:+d}")
    sections.append("\n".join(rep_lines))

    await message.reply("\n\n".join(sections))
