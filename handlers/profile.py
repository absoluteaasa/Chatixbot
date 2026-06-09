"""
Модуль профиля:
  кто я / кто ты — карточка профиля с графиком активности
  +описание [текст]
  +имя, +возраст, +город, +страна, +хобби
  Кнопки: Описание, Анкета
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.types import (
    BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup,
    Message, CallbackQuery,
)

from database import repo
from utils.helpers import mention_user, format_balance

logger = logging.getLogger(__name__)
router = Router()

# ─── Генерация графика активности (без matplotlib — чистый SVG) ───────────────

def generate_activity_svg(activity_data: list, days: int = 8) -> bytes:
    """Генерирует SVG-график активности по дням."""
    from datetime import date, timedelta

    today = datetime.utcnow().date()
    # Строим словарь {date: count}
    data_map = {}
    for rec in activity_data:
        d = rec.date.date() if hasattr(rec.date, 'date') else rec.date
        data_map[d] = rec.messages

    dates = [(today - timedelta(days=days - 1 - i)) for i in range(days)]
    values = [data_map.get(d, 0) for d in dates]
    max_val = max(values) if max(values) > 0 else 1

    W, H = 400, 200
    PAD_L, PAD_R, PAD_T, PAD_B = 40, 10, 20, 30
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    bar_w = chart_w / days
    gap = bar_w * 0.15

    bars = []
    for i, (d, v) in enumerate(zip(dates, values)):
        bh = int((v / max_val) * chart_h)
        x = PAD_L + i * bar_w + gap
        y = PAD_T + chart_h - bh
        w = bar_w - gap * 2
        color = "#e74c3c" if d == today else "#2ecc71"
        bars.append(
            f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{bh}" fill="{color}" rx="3"/>'
        )
        # Подпись даты
        label = d.strftime("%d.%m")
        lx = x + w / 2
        bars.append(
            f'<text x="{lx:.1f}" y="{H - 5}" text-anchor="middle" '
            f'font-size="9" fill="#aaa">{label}</text>'
        )

    # Линии сетки
    grid = []
    for i in range(5):
        gy = PAD_T + (chart_h // 4) * i
        gv = int(max_val * (1 - i / 4))
        grid.append(f'<line x1="{PAD_L}" y1="{gy}" x2="{W - PAD_R}" y2="{gy}" stroke="#333" stroke-width="1"/>')
        grid.append(f'<text x="{PAD_L - 4}" y="{gy + 4}" text-anchor="end" font-size="9" fill="#888">{gv}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1a1a2e">
  <text x="{W//2}" y="14" text-anchor="middle" font-size="11" fill="#ccc">Статистика активности</text>
  {"".join(grid)}
  {"".join(bars)}
</svg>'''
    return svg.encode("utf-8")


def svg_to_png_bytes(svg_bytes: bytes) -> bytes:
    """Конвертирует SVG в PNG через cairosvg если доступен, иначе возвращает SVG."""
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg_bytes, output_width=400, output_height=200)
    except ImportError:
        # Возвращаем SVG как есть — Telegram не покажет, но не упадёт
        return svg_bytes


# ─── Ранги ────────────────────────────────────────────────────────────────────

def get_rank(messages: int) -> str:
    if messages >= 10000: return "👑 Легенда"
    if messages >= 5000:  return "💎 Мастер"
    if messages >= 2000:  return "🏆 Эксперт"
    if messages >= 1000:  return "⭐ Ветеран"
    if messages >= 500:   return "🔥 Активный"
    if messages >= 100:   return "📝 Участник"
    return "🌱 Новичок"


def format_last_active(last_rec) -> str:
    if not last_rec:
        return "нет данных"
    diff = datetime.utcnow() - last_rec.date
    if diff.seconds < 60:
        return "только что"
    if diff.seconds < 3600:
        return f"{diff.seconds // 60} минут назад"
    if diff.days == 0:
        return f"{diff.seconds // 3600} ч. назад"
    return f"{diff.days} дн. назад"


def format_count(n: int) -> str:
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


# ─── Профиль (кто я / кто ты) ────────────────────────────────────────────────

async def show_profile(message: Message, target_user) -> None:
    """Формирует и отправляет карточку профиля."""
    chat_id = message.chat.id
    user_id = target_user.id

    await repo.get_or_create_user(user_id, target_user.username, target_user.full_name)
    db_user = await repo.get_user(user_id)
    if not db_user:
        await message.reply("❌ Пользователь не найден.")
        return

    # Активность
    activity = await repo.get_activity_last_days(user_id, chat_id, days=8)
    last_active = await repo.get_last_activity(user_id, chat_id)

    # Подсчёт активности за периоды
    now = datetime.utcnow()
    act_day = sum(r.messages for r in activity if (now - r.date).days < 1)
    act_week = sum(r.messages for r in activity if (now - r.date).days < 7)
    act_month = db_user.messages_count  # всего — приблизительно месяц

    # Брак
    marriage = await repo.get_marriage(user_id, chat_id)
    marriage_str = ""
    if marriage:
        partner_id = marriage.user2_id if marriage.user1_id == user_id else marriage.user1_id
        partner = await repo.get_user(partner_id)
        if partner:
            marriage_str = f"\n💑 Партнёр: {partner.full_name or partner.username}"

    # Статус в чате
    try:
        member = await message.bot.get_chat_member(chat_id, user_id)
        status_map = {
            "creator": "👑 Владелец чата",
            "administrator": "🛡️ Администратор",
            "member": "👤 Участник",
            "restricted": "🔇 Ограничен",
            "left": "🚪 Покинул чат",
            "banned": "🔨 Заблокирован",
        }
        chat_status = status_map.get(member.status, "👤 Участник")
    except Exception:
        chat_status = "👤 Участник"

    rank = get_rank(db_user.messages_count)
    joined = db_user.created_at.strftime("%d.%m.%Y")
    days_in = (now - db_user.created_at).days
    hours_in = int((now - db_user.created_at).total_seconds() // 3600) % 24

    text = (
        f"👤 Это пользователь\n"
        f"<b>{mention_user(target_user)}</b>\n"
        f"{chat_status}\n\n"
        f"{rank}\n"
        f"💰 Баланс: {format_balance(db_user.balance)}\n"
        f"⭐ Репутация: ✨ {max(0,db_user.reputation)} | 💀 {abs(min(0,db_user.reputation))}\n"
        f"⚠️ Варны: {db_user.warnings}\n"
        f"📅 Первое появление: {joined} ({days_in} дн. {hours_in} ч)\n"
        f"🕐 Последний актив: {format_last_active(last_active)}\n"
        f"📊 Актив (д|н|всего): {format_count(act_day)} | {format_count(act_week)} | {format_count(act_month)}"
        f"{marriage_str}"
    )

    # Кнопки
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📋 Описание", callback_data=f"profile_desc:{user_id}"),
            InlineKeyboardButton(text="📝 Анкета", callback_data=f"profile_anketa:{user_id}"),
        ]
    ])

    # Генерируем график
    svg = generate_activity_svg(activity)
    try:
        png = svg_to_png_bytes(svg)
        photo = BufferedInputFile(png, filename="activity.png")
        await message.reply_photo(photo=photo, caption=text, reply_markup=kb)
    except Exception:
        # Если не вышло с картинкой — просто текст
        await message.reply(text, reply_markup=kb)


@router.message(F.text.lower().in_({"кто я"}))
async def cmd_who_am_i(message: Message) -> None:
    await show_profile(message, message.from_user)


@router.message(F.text.lower().in_({"кто ты"}) & F.reply_to_message)
async def cmd_who_is(message: Message) -> None:
    if message.reply_to_message and message.reply_to_message.from_user:
        await show_profile(message, message.reply_to_message.from_user)
    else:
        await message.reply("ℹ️ Ответь на сообщение пользователя и напиши <b>кто ты</b>")


# ─── Callback: Описание ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("profile_desc:"))
async def cb_description(call: CallbackQuery) -> None:
    user_id = int(call.data.split(":")[1])
    profile = await repo.get_profile(user_id)
    db_user = await repo.get_user(user_id)
    name = db_user.full_name if db_user else str(user_id)

    desc = profile.description or "<i>Описание не заполнено</i>"
    await call.answer()
    await call.message.answer(
        f"📋 <b>Описание {name}:</b>\n\n{desc}"
    )


# ─── Callback: Анкета ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("profile_anketa:"))
async def cb_anketa(call: CallbackQuery) -> None:
    user_id = int(call.data.split(":")[1])
    profile = await repo.get_profile(user_id)
    db_user = await repo.get_user(user_id)
    name = db_user.full_name if db_user else str(user_id)

    lines = [f"📝 <b>Анкета {name}:</b>\n"]
    lines.append(f"👤 Имя: {profile.name or '—'}")
    lines.append(f"🎂 Возраст: {profile.age or '—'}")
    lines.append(f"🏙️ Город: {profile.city or '—'}")
    lines.append(f"🌍 Страна: {profile.country or '—'}")
    lines.append(f"🎮 Хобби: {profile.hobby or '—'}")

    await call.answer()
    await call.message.answer("\n".join(lines))


# ─── Редактирование профиля ───────────────────────────────────────────────────

PROFILE_FIELDS = {
    "+описание": "description",
    "+имя": "name",
    "+возраст": "age",
    "+город": "city",
    "+страна": "country",
    "+хобби": "hobby",
}


@router.message(F.text.lower().regexp(r"^\+(описание|имя|возраст|город|страна|хобби)\s+.+", flags=2))
async def cmd_set_profile_field(message: Message) -> None:
    text = message.text or ""
    text_lower = text.lower()

    field_key = None
    field_db = None
    for key, db_key in PROFILE_FIELDS.items():
        if text_lower.startswith(key + " "):
            field_key = key
            field_db = db_key
            break

    if not field_key:
        return

    value = text[len(field_key):].strip()
    if not value:
        await message.reply(f"ℹ️ Укажи значение: <code>{field_key} [текст]</code>")
        return

    if len(value) > 200:
        await message.reply("❌ Слишком длинный текст (макс. 200 символов).")
        return

    user = message.from_user
    await repo.get_or_create_user(user.id, user.username, user.full_name)
    await repo.update_profile(user.id, **{field_db: value})

    field_names = {
        "description": "Описание",
        "name": "Имя",
        "age": "Возраст",
        "city": "Город",
        "country": "Страна",
        "hobby": "Хобби",
    }
    await message.reply(f"✅ {field_names[field_db]} обновлено!")
