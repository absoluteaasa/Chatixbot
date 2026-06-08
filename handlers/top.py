"""
!топ — топ активности с SVG графиком
!топ [N] — топ N пользователей за день
!топ вся — топ за все время
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from aiogram import F, Router
from aiogram.types import Message, BufferedInputFile
from database import repo

logger = logging.getLogger(__name__)
router = Router()


def generate_top_svg(data: list[tuple[str, int]], title: str) -> bytes:
    if not data:
        return b""
    max_val = max(v for _, v in data) or 1
    W, H = 500, 300
    PAD_L, PAD_R, PAD_T, PAD_B = 120, 20, 40, 20
    chart_w = W - PAD_L - PAD_R
    chart_h = H - PAD_T - PAD_B
    n = len(data)
    bar_h = chart_h / n
    gap = bar_h * 0.15

    bars = []
    for i, (name, val) in enumerate(data):
        bw = int((val / max_val) * chart_w)
        y = PAD_T + i * bar_h + gap
        h = bar_h - gap * 2
        color = "#e74c3c" if i == 0 else "#2ecc71"
        bars.append(f'<rect x="{PAD_L}" y="{y:.1f}" width="{bw}" height="{h:.1f}" fill="{color}" rx="3"/>')
        # Имя
        bars.append(f'<text x="{PAD_L - 6}" y="{y + h/2 + 4:.1f}" text-anchor="end" font-size="11" fill="#ddd">{name[:15]}</text>')
        # Значение
        bars.append(f'<text x="{PAD_L + bw + 4}" y="{y + h/2 + 4:.1f}" font-size="11" fill="#aaa">{val}</text>')

    medals = ["🥇", "🥈", "🥉"] + [""] * 7
    medal_els = []
    for i, (name, val) in enumerate(data[:3]):
        y = PAD_T + i * bar_h + bar_h/2 + 4
        medal_els.append(f'<text x="4" y="{y:.1f}" font-size="14">{medals[i]}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" style="background:#1a1a2e">
  <text x="{W//2}" y="24" text-anchor="middle" font-size="13" fill="#fff" font-weight="bold">{title}</text>
  {"".join(bars)}
  {"".join(medal_els)}
</svg>'''
    return svg.encode("utf-8")


def svg_to_png(svg: bytes) -> bytes:
    try:
        import cairosvg
        return cairosvg.svg2png(bytestring=svg, output_width=500, output_height=300)
    except ImportError:
        return svg


@router.message(F.text.regexp(r"^[!.]?топ(\s|$)", flags=2))
async def cmd_top(message: Message) -> None:
    text = (message.text or "").strip().lower()
    import re
    match = re.match(r"^[!.]?топ\s*(.*)", text)
    arg = match.group(1).strip() if match else ""

    chat_id = message.chat.id

    if arg == "вся" or arg == "все":
        # Топ за все время
        top = await repo.get_top_users(limit=10)
        active = top["active"]
        data = [(u.full_name or u.username or str(u.id), u.messages_count) for u in active if u.messages_count > 0]
        title = "Топ активности — всё время"
    elif arg.isdigit():
        # Топ N за день
        limit = min(int(arg), 10)
        today_top = await repo.get_top_active_today(chat_id, limit=limit)
        data = []
        for user_id, total in today_top:
            u = await repo.get_user(user_id)
            name = u.full_name or u.username if u else str(user_id)
            data.append((name, int(total)))
        title = f"Топ {limit} активности — сегодня"
    else:
        # Обычный топ за день
        today_top = await repo.get_top_active_today(chat_id, limit=10)
        data = []
        for user_id, total in today_top:
            u = await repo.get_user(user_id)
            name = u.full_name or u.username if u else str(user_id)
            data.append((name, int(total)))
        title = "Топ активности — сегодня"

    if not data:
        await message.reply("📊 Пока нет данных об активности.")
        return

    svg = generate_top_svg(data, title)
    try:
        png = svg_to_png(svg)
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
        lines = [f"📊 <b>{title}</b>\n"]
        for i, (name, val) in enumerate(data):
            lines.append(f"{medals[i]} {name} — <b>{val}</b> сообщ.")
        photo = BufferedInputFile(png, filename="top.png")
        await message.reply_photo(photo=photo, caption="\n".join(lines))
    except Exception:
        medals = ["🥇", "🥈", "🥉"] + ["🔹"] * 7
        lines = [f"📊 <b>{title}</b>\n"]
        for i, (name, val) in enumerate(data):
            lines.append(f"{medals[i]} {name} — <b>{val}</b> сообщ.")
        await message.reply("\n".join(lines))
