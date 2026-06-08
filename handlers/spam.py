"""
Спамбаза и управление запрещёнными словами
!спам — просмотр
!спам+ [слово] — добавить
!спам- [слово] — удалить
"""
from __future__ import annotations
import logging
from aiogram import F, Router
from aiogram.types import Message
from database import repo
from utils.helpers import mention_user

logger = logging.getLogger(__name__)
router = Router()

CMD_PREFIXES = ("!спам", ".спам", "спам")


def _starts_with(text: str, cmd: str) -> bool:
    t = text.lower().strip()
    return t == cmd or t.startswith(cmd + " ") or t.startswith(cmd + "+") or t.startswith(cmd + "-")


@router.message(F.text.lower().regexp(r"^[!.]?спам(\+|-|\s|$)", flags=2))
async def cmd_spam(message: Message, is_admin: bool = False) -> None:
    text = (message.text or "").strip()
    text_lower = text.lower()

    # !спам+ слово — добавить
    for prefix in ("!спам+", ".спам+", "спам+"):
        if text_lower.startswith(prefix):
            if not is_admin:
                await message.reply("⛔ Только для администраторов!")
                return
            word = text[len(prefix):].strip().lower()
            if not word:
                await message.reply("ℹ️ Укажи слово: <code>!спам+ [слово]</code>")
                return
            await repo.add_spam_entry(message.chat.id, word, message.from_user.id)
            # Также добавляем в chat_settings forbidden_words
            cs = await repo.get_chat_settings(message.chat.id)
            existing = set(cs.forbidden_words.split("|")) if cs.forbidden_words else set()
            existing.add(word)
            await repo.update_chat_settings(message.chat.id, forbidden_words="|".join(filter(None, existing)))
            await message.reply(f"✅ Слово <code>{word}</code> добавлено в спамбазу.")
            return

    # !спам- слово — удалить
    for prefix in ("!спам-", ".спам-", "спам-"):
        if text_lower.startswith(prefix):
            if not is_admin:
                await message.reply("⛔ Только для администраторов!")
                return
            word = text[len(prefix):].strip().lower()
            if not word:
                await message.reply("ℹ️ Укажи слово: <code>!спам- [слово]</code>")
                return
            ok = await repo.remove_spam_entry(message.chat.id, word)
            # Удаляем из chat_settings
            cs = await repo.get_chat_settings(message.chat.id)
            existing = set(cs.forbidden_words.split("|")) if cs.forbidden_words else set()
            existing.discard(word)
            await repo.update_chat_settings(message.chat.id, forbidden_words="|".join(filter(None, existing)))
            if ok:
                await message.reply(f"✅ Слово <code>{word}</code> удалено из спамбазы.")
            else:
                await message.reply(f"❌ Слово <code>{word}</code> не найдено в спамбазе.")
            return

    # !спам — просмотр
    entries = await repo.get_spam_entries(message.chat.id)
    cs = await repo.get_chat_settings(message.chat.id)
    fw = [w for w in cs.forbidden_words.split("|") if w]

    if not entries and not fw:
        await message.reply(
            "🚫 <b>Спамбаза пуста</b>\n\n"
            "Добавить: <code>!спам+ [слово]</code>\n"
            "Удалить: <code>!спам- [слово]</code>"
        )
        return

    all_words = set([e.pattern for e in entries] + fw)
    lines = [f"🚫 <b>Спамбаза чата</b> ({len(all_words)} слов)\n"]
    for i, w in enumerate(sorted(all_words), 1):
        lines.append(f"{i}. <code>{w}</code>")
    lines.append(f"\n<i>Добавить: !спам+ [слово] | Удалить: !спам- [слово]</i>")
    await message.reply("\n".join(lines))
