"""
Модуль экономики и мини-игр:
  /баланс, /бонус, /перевод
  Казино (рулетка), Кости, Ставки
  РП-команды: !обнять, !ударить, !поцеловать
"""

from __future__ import annotations

import logging
import random
from typing import NamedTuple

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from config import settings
from database import repo
from utils.helpers import extract_target, format_balance, mention_user

logger = logging.getLogger(__name__)
router = Router()

# ─── Баланс ───────────────────────────────────────────────────────────────────

@router.message(Command("баланс"))
async def cmd_balance(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    db_user = await repo.get_user(user.id)
    balance = db_user.balance if db_user else settings.STARTING_BALANCE

    await message.reply(
        f"💰 Баланс {mention_user(user)}:\n"
        f"{format_balance(balance)}"
    )


# ─── Ежедневный бонус ─────────────────────────────────────────────────────────

@router.message(Command("бонус"))
async def cmd_bonus(message: Message) -> None:
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    success, next_time = await repo.claim_daily_bonus(user.id, settings.DAILY_BONUS)

    if success:
        logger.info(f"[BONUS] Пользователь {user.id} получил ежедневный бонус")
        await message.reply(
            f"🎁 {mention_user(user)}, ты получил ежедневный бонус!\n"
            f"+{format_balance(settings.DAILY_BONUS)} 🍬"
        )
    else:
        from datetime import datetime
        remaining = next_time - datetime.utcnow() if next_time else None
        if remaining:
            h, rem = divmod(int(remaining.total_seconds()), 3600)
            m = rem // 60
            await message.reply(
                f"⏳ {mention_user(user)}, следующий бонус через "
                f"<b>{h}ч {m}мин</b>."
            )


# ─── Перевод ──────────────────────────────────────────────────────────────────

@router.message(Command("перевод"))
async def cmd_transfer(message: Message) -> None:
    """
    /перевод [сумма] — ответ на сообщение или упоминание
    /перевод 100 @user
    """
    user = message.from_user
    target = extract_target(message)

    if not target:
        await message.reply(
            "ℹ️ Использование: ответь на сообщение пользователя и напиши\n"
            "<code>/перевод 100</code>"
        )
        return

    if target.id == user.id:
        await message.reply("🤨 Себе переводить нельзя.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("ℹ️ Укажи сумму: <code>/перевод 100</code>")
        return

    try:
        amount = int(parts[1])
    except ValueError:
        await message.reply("❌ Сумма должна быть целым числом.")
        return

    if amount <= 0:
        await message.reply("❌ Сумма должна быть положительной.")
        return

    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await repo.get_or_create_user(target.id, target.username, target.full_name)

    success = await repo.transfer_balance(user.id, target.id, amount)

    if success:
        logger.info(f"[TRANSFER] {user.id} → {target.id}: {amount}")
        await message.reply(
            f"✅ {mention_user(user)} перевёл {format_balance(amount)} пользователю {mention_user(target)}!"
        )
    else:
        await message.reply("❌ Недостаточно ирисок для перевода!")


# ─── Казино (рулетка) ─────────────────────────────────────────────────────────

ROULETTE_MULTIPLIER = {
    "red": 2,    # красный (18 чисел)
    "black": 2,  # чёрный (18 чисел)
    "green": 14, # зелёный (0) — редко
    "even": 2,   # чётный
    "odd": 2,    # нечётный
}

RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}


class SpinResult(NamedTuple):
    number: int
    color: str


def _spin_roulette() -> SpinResult:
    number = random.randint(0, 36)
    if number == 0:
        color = "green"
    elif number in RED_NUMBERS:
        color = "red"
    else:
        color = "black"
    return SpinResult(number, color)


COLOR_EMOJI = {"red": "🔴", "black": "⚫", "green": "🟢"}


@router.message(Command("казино"))
async def cmd_casino(message: Message) -> None:
    """
    /казино [ставка] [red|black|green|even|odd|число 0-36]
    Пример: /казино 50 red
    """
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply(
            "🎰 <b>Казино — Рулетка</b>\n\n"
            "Использование: <code>/казино [ставка] [цвет/число]</code>\n"
            "Варианты: <code>red, black, green, even, odd, 0-36</code>\n\n"
            "Выигрыши: red/black/even/odd ×2 | green ×14 | число ×35"
        )
        return

    try:
        bet = int(parts[1])
    except ValueError:
        await message.reply("❌ Ставка должна быть числом.")
        return

    if bet <= 0:
        await message.reply("❌ Ставка должна быть > 0.")
        return

    db_user = await repo.get_user(user.id)
    if not db_user or db_user.balance < bet:
        await message.reply(f"❌ Недостаточно ирисок! Твой баланс: {format_balance(db_user.balance if db_user else 0)}")
        return

    choice = parts[2].lower()
    result = _spin_roulette()

    # Определяем победу
    win = False
    multiplier = 0

    if choice in ("red", "black", "green"):
        if choice == result.color:
            win = True
            multiplier = ROULETTE_MULTIPLIER[choice]
    elif choice == "even":
        if result.number != 0 and result.number % 2 == 0:
            win = True
            multiplier = 2
    elif choice == "odd":
        if result.number % 2 == 1:
            win = True
            multiplier = 2
    elif choice.isdigit() and 0 <= int(choice) <= 36:
        if int(choice) == result.number:
            win = True
            multiplier = 35
    else:
        await message.reply("❌ Неверный вариант ставки. Используй: red, black, green, even, odd или число 0-36")
        return

    color_e = COLOR_EMOJI.get(result.color, "⚪")

    if win:
        profit = bet * multiplier
        await repo.update_balance(user.id, profit - bet)  # выигрыш минус ставка уже снята
        # Точнее: сначала снимаем ставку, потом начисляем выигрыш
        await repo.update_balance(user.id, -bet)
        await repo.update_balance(user.id, profit)
        logger.info(f"[CASINO WIN] {user.id} поставил {bet}, выиграл {profit}")
        await message.reply(
            f"🎰 Шарик остановился на {color_e} <b>{result.number}</b>!\n\n"
            f"🎉 {mention_user(user)}, ты <b>выиграл</b> {format_balance(profit)}! (×{multiplier})"
        )
    else:
        await repo.update_balance(user.id, -bet)
        logger.info(f"[CASINO LOSE] {user.id} поставил {bet}")
        await message.reply(
            f"🎰 Шарик остановился на {color_e} <b>{result.number}</b>!\n\n"
            f"😔 {mention_user(user)}, ты <b>проиграл</b> {format_balance(bet)}."
        )


# ─── Кости ────────────────────────────────────────────────────────────────────

@router.message(Command("кости"))
async def cmd_dice(message: Message) -> None:
    """
    /кости [ставка] — бросок двух кубиков против бота.
    Если сумма игрока > суммы бота — выигрыш ×2.
    Ничья — возврат ставки.
    """
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("🎲 Использование: <code>/кости [ставка]</code>")
        return

    try:
        bet = int(parts[1])
    except ValueError:
        await message.reply("❌ Ставка должна быть числом.")
        return

    if bet <= 0:
        await message.reply("❌ Ставка > 0.")
        return

    db_user = await repo.get_user(user.id)
    if not db_user or db_user.balance < bet:
        await message.reply("❌ Недостаточно ирисок!")
        return

    player_dice = (random.randint(1, 6), random.randint(1, 6))
    bot_dice = (random.randint(1, 6), random.randint(1, 6))
    player_sum = sum(player_dice)
    bot_sum = sum(bot_dice)

    dice_faces = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

    lines = [
        f"🎲 <b>Кости</b>",
        f"",
        f"Ты: {dice_faces[player_dice[0]]} {dice_faces[player_dice[1]]} = <b>{player_sum}</b>",
        f"Бот: {dice_faces[bot_dice[0]]} {dice_faces[bot_dice[1]]} = <b>{bot_sum}</b>",
        f"",
    ]

    if player_sum > bot_sum:
        await repo.update_balance(user.id, bet)
        lines.append(f"🎉 {mention_user(user)} победил! +{format_balance(bet)}")
    elif player_sum < bot_sum:
        await repo.update_balance(user.id, -bet)
        lines.append(f"😔 Бот победил! -{format_balance(bet)}")
    else:
        lines.append("🤝 Ничья! Ставка возвращена.")

    await message.reply("\n".join(lines))


# ─── Ставки (coinflip) ───────────────────────────────────────────────────────

@router.message(Command("ставка"))
async def cmd_coinflip(message: Message) -> None:
    """
    /ставка [сумма] [орёл|решка] — подбрасывает монету.
    """
    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)

    parts = message.text.split()
    if len(parts) < 3:
        await message.reply(
            "🪙 Использование: <code>/ставка [сумма] [орёл|решка]</code>"
        )
        return

    try:
        bet = int(parts[1])
    except ValueError:
        await message.reply("❌ Ставка — число.")
        return

    choice = parts[2].lower()
    if choice not in ("орёл", "решка"):
        await message.reply("❌ Только <code>орёл</code> или <code>решка</code>!")
        return

    db_user = await repo.get_user(user.id)
    if not db_user or db_user.balance < bet:
        await message.reply("❌ Недостаточно ирисок!")
        return

    result = random.choice(["орёл", "решка"])
    coin_emoji = "🦅" if result == "орёл" else "🌿"

    if choice == result:
        await repo.update_balance(user.id, bet)
        await message.reply(
            f"🪙 Монета: <b>{coin_emoji} {result}</b>!\n\n"
            f"🎉 {mention_user(user)}, ты угадал! +{format_balance(bet)}"
        )
    else:
        await repo.update_balance(user.id, -bet)
        await message.reply(
            f"🪙 Монета: <b>{coin_emoji} {result}</b>!\n\n"
            f"😔 {mention_user(user)}, не угадал. -{format_balance(bet)}"
        )


# ─── РП-команды ───────────────────────────────────────────────────────────────

RP_ACTIONS = {
    "обнять": {
        "emoji": "🤗",
        "phrases": [
            "{actor} крепко обнимает {target}!",
            "{actor} нежно обнимает {target}~",
            "{actor} обхватывает {target} руками и не отпускает!",
        ],
    },
    "поцеловать": {
        "emoji": "💋",
        "phrases": [
            "{actor} целует {target} в щёчку!",
            "{actor} нежно целует {target}~ 💕",
            "{actor} дарит {target} воздушный поцелуй! 😘",
        ],
    },
    "ударить": {
        "emoji": "👊",
        "phrases": [
            "{actor} бьёт {target} по лбу!",
            "{actor} хлопает {target} газетой!",
            "{actor} даёт {target} подзатыльник!",
        ],
    },
    "погладить": {
        "emoji": "✋",
        "phrases": [
            "{actor} гладит {target} по голове~",
            "{actor} треплет {target} за волосы!",
        ],
    },
    "укусить": {
        "emoji": "😬",
        "phrases": [
            "{actor} кусает {target}! Ай!",
            "{actor} слегка покусывает {target}~",
        ],
    },
    "подмигнуть": {
        "emoji": "😉",
        "phrases": [
            "{actor} подмигивает {target}~",
            "{actor} игриво подмигивает {target}!",
        ],
    },
}


@router.message(F.text.regexp(r"^[!/.]?(обнять|поцеловать|ударить|погладить|укусить|подмигнуть)(\s|$)", flags=2))
async def cmd_rp(message: Message) -> None:
    """Обрабатывает все РП-команды (!, /, . или без префикса)."""
    import re
    text = (message.text or "").lower().strip().lstrip("!/.")
    action = None
    for key in RP_ACTIONS:
        if text.startswith(key):
            action = key
            break

    if not action:
        return

    # Определяем цель: ответ на сообщение или @упоминание в тексте
    target = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
    else:
        target = extract_target(message)

    actor = message.from_user
    action_data = RP_ACTIONS[action]

    actor_mention = mention_user(actor)
    if target:
        target_mention = mention_user(target)
    else:
        target_mention = "<b>всех</b>"

    phrase = random.choice(action_data["phrases"]).format(
        actor=actor_mention, target=target_mention
    )
    await message.reply(f"{action_data['emoji']} {phrase}")
