"""
Репозиторий Chatix
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.db import *

logger = logging.getLogger(__name__)

ROLE_NAMES = {
    0: "Без должности",
    1: "⭐ Младший модератор",
    2: "⭐⭐ Старший модератор",
    3: "⭐⭐⭐ Младший администратор",
    4: "⭐⭐⭐⭐ Старший администратор",
    5: "⭐⭐⭐⭐⭐ Владелец",
}

TREE_NAMES = {
    1: "Модерация",
    2: "Экономика и игры",
    3: "Браки",
    4: "Репутация",
    5: "РП-команды",
    6: "Профиль",
    7: "Управление",
    8: "Спамбаза",
    9: "Магазин",
    10: "Уровни и ачивки",
    11: "Банк и работа",
    12: "Аукцион",
    13: "Кланы",
    14: "Дружба и подарки",
    15: "Тикеты",
    16: "Аналитика",
}

def session_scope():
    return async_session()

async def get_or_create_user(user_id: int, username, full_name: str):
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            user = User(id=user_id, username=username, full_name=full_name, balance=50)
            s.add(user)
            await s.commit()
            await s.refresh(user)
        else:
            if user.full_name != full_name or user.username != username:
                user.full_name = full_name
                user.username = username
                await s.commit()
        return user

async def get_user(user_id: int):
    async with session_scope() as s:
        return await s.get(User, user_id)

async def claim_install_bonus(user_id: int) -> tuple[bool, int]:
    """Выдаёт 50 ирисок за установку — только 1 раз. Возвращает (success, new_balance)."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user or user.install_bonus_claimed:
            return False, user.balance if user else 0
        user.install_bonus_claimed = True
        user.balance += 50
        await s.commit()
        return True, user.balance

async def update_balance(user_id: int, delta: int) -> int:
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return 0
        user.balance = max(0, user.balance + delta)
        await s.commit()
        return user.balance

async def increment_messages(user_id: int) -> None:
    async with session_scope() as s:
        await s.execute(update(User).where(User.id == user_id).values(messages_count=User.messages_count + 1))
        await s.commit()

async def claim_daily_bonus(user_id: int, amount: int):
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return False, None
        now = datetime.utcnow()
        if user.last_bonus and (now - user.last_bonus) < timedelta(hours=24):
            return False, user.last_bonus + timedelta(hours=24)
        user.balance += amount
        user.last_bonus = now
        await s.commit()
        return True, now + timedelta(hours=24)

async def transfer_balance(sender_id: int, receiver_id: int, amount: int) -> bool:
    async with session_scope() as s:
        sender = await s.get(User, sender_id)
        receiver = await s.get(User, receiver_id)
        if not sender or not receiver or sender.balance < amount:
            return False
        sender.balance -= amount
        receiver.balance += amount
        s.add(Transfer(sender_id=sender_id, receiver_id=receiver_id, amount=amount))
        await s.commit()
        return True

async def add_warning(user_id: int, chat_id: int, reason: str, issued_by: int) -> int:
    async with session_scope() as s:
        s.add(Warning(user_id=user_id, chat_id=chat_id, reason=reason, issued_by=issued_by))
        user = await s.get(User, user_id)
        if user:
            user.warnings += 1
        await s.commit()
        return user.warnings if user else 1

async def get_warnings(user_id: int, chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(Warning).where(and_(Warning.user_id == user_id, Warning.chat_id == chat_id)))
        return list(result.scalars().all())

async def clear_warnings(user_id: int, chat_id: int) -> None:
    async with session_scope() as s:
        await s.execute(delete(Warning).where(and_(Warning.user_id == user_id, Warning.chat_id == chat_id)))
        user = await s.get(User, user_id)
        if user:
            user.warnings = 0
        await s.commit()

async def vote_reputation(voter_id: int, target_id: int, chat_id: int, value: int):
    async with session_scope() as s:
        today = datetime.utcnow().date()
        existing = await s.execute(select(ReputationVote).where(and_(
            ReputationVote.voter_id == voter_id, ReputationVote.target_id == target_id,
            ReputationVote.chat_id == chat_id, func.date(ReputationVote.created_at) == today,
        )))
        if existing.scalar():
            return False, "Ты уже голосовал за этого пользователя сегодня!"
        s.add(ReputationVote(voter_id=voter_id, target_id=target_id, chat_id=chat_id, value=value))
        user = await s.get(User, target_id)
        if user:
            user.reputation += value
        await s.commit()
        return True, ""

async def get_top_users(limit: int = 10):
    async with session_scope() as s:
        rich = (await s.execute(select(User).order_by(User.balance.desc()).limit(limit))).scalars().all()
        active = (await s.execute(select(User).order_by(User.messages_count.desc()).limit(limit))).scalars().all()
        reputable = (await s.execute(select(User).order_by(User.reputation.desc()).limit(limit))).scalars().all()
        return {"rich": list(rich), "active": list(active), "reputable": list(reputable)}

async def get_top_active_today(chat_id: int, limit: int = 10):
    async with session_scope() as s:
        today = datetime.utcnow().date()
        result = await s.execute(
            select(DailyActivity.user_id, func.sum(DailyActivity.messages).label("total"))
            .where(and_(DailyActivity.chat_id == chat_id, func.date(DailyActivity.date) == today))
            .group_by(DailyActivity.user_id)
            .order_by(func.sum(DailyActivity.messages).desc())
            .limit(limit)
        )
        return result.all()

async def get_marriage(user_id: int, chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(Marriage).where(and_(
            or_(Marriage.user1_id == user_id, Marriage.user2_id == user_id),
            Marriage.chat_id == chat_id,
        )))
        return result.scalar_one_or_none()

async def create_marriage(user1_id: int, user2_id: int, chat_id: int):
    async with session_scope() as s:
        marriage = Marriage(user1_id=user1_id, user2_id=user2_id, chat_id=chat_id)
        s.add(marriage)
        await s.commit()
        await s.refresh(marriage)
        return marriage

async def divorce(user_id: int, chat_id: int) -> bool:
    async with session_scope() as s:
        result = await s.execute(select(Marriage).where(and_(
            or_(Marriage.user1_id == user_id, Marriage.user2_id == user_id),
            Marriage.chat_id == chat_id,
        )))
        marriage = result.scalar_one_or_none()
        if not marriage:
            return False
        await s.delete(marriage)
        await s.commit()
        return True

async def get_all_marriages(chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(Marriage).where(Marriage.chat_id == chat_id))
        return list(result.scalars().all())

async def get_chat_settings(chat_id: int):
    async with session_scope() as s:
        settings = await s.get(ChatSettings, chat_id)
        if not settings:
            try:
                settings = ChatSettings(chat_id=chat_id)
                s.add(settings)
                await s.commit()
            except Exception:
                await s.rollback()
                settings = await s.get(ChatSettings, chat_id)
        return settings

async def update_chat_settings(chat_id: int, **kwargs) -> None:
    async with session_scope() as s:
        settings = await s.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(chat_id=chat_id)
            s.add(settings)
        for key, val in kwargs.items():
            setattr(settings, key, val)
        await s.commit()

async def get_profile(user_id: int):
    async with session_scope() as s:
        p = await s.get(UserProfile, user_id)
        if not p:
            p = UserProfile(user_id=user_id)
            s.add(p)
            await s.commit()
        return p

async def update_profile(user_id: int, **kwargs) -> None:
    async with session_scope() as s:
        p = await s.get(UserProfile, user_id)
        if not p:
            p = UserProfile(user_id=user_id)
            s.add(p)
        for k, v in kwargs.items():
            setattr(p, k, v)
        p.updated_at = datetime.utcnow()
        await s.commit()

async def record_daily_activity(user_id: int, chat_id: int) -> None:
    async with session_scope() as s:
        today = datetime.utcnow().date()
        result = await s.execute(select(DailyActivity).where(and_(
            DailyActivity.user_id == user_id, DailyActivity.chat_id == chat_id,
            func.date(DailyActivity.date) == today,
        )))
        rec = result.scalar_one_or_none()
        if rec:
            rec.messages += 1
        else:
            s.add(DailyActivity(user_id=user_id, chat_id=chat_id, date=datetime.utcnow(), messages=1))
        await s.commit()

async def get_activity_last_days(user_id: int, chat_id: int, days: int = 8):
    async with session_scope() as s:
        since = datetime.utcnow() - timedelta(days=days)
        result = await s.execute(select(DailyActivity).where(and_(
            DailyActivity.user_id == user_id, DailyActivity.chat_id == chat_id,
            DailyActivity.date >= since,
        )).order_by(DailyActivity.date))
        return list(result.scalars().all())

async def get_last_activity(user_id: int, chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(DailyActivity).where(and_(
            DailyActivity.user_id == user_id, DailyActivity.chat_id == chat_id,
        )).order_by(DailyActivity.date.desc()).limit(1))
        return result.scalar_one_or_none()

async def get_user_role(user_id: int, chat_id: int) -> int:
    async with session_scope() as s:
        result = await s.execute(select(UserRole).where(and_(UserRole.user_id == user_id, UserRole.chat_id == chat_id)))
        rec = result.scalar_one_or_none()
        return rec.role if rec else 0

async def set_user_role(user_id: int, chat_id: int, role: int) -> None:
    async with session_scope() as s:
        result = await s.execute(select(UserRole).where(and_(UserRole.user_id == user_id, UserRole.chat_id == chat_id)))
        rec = result.scalar_one_or_none()
        if rec:
            rec.role = role
        else:
            s.add(UserRole(user_id=user_id, chat_id=chat_id, role=role))
        await s.commit()

async def get_all_roles(chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(UserRole).where(and_(UserRole.chat_id == chat_id, UserRole.role > 0)).order_by(UserRole.role.desc()))
        return list(result.scalars().all())

async def get_tree(chat_id: int, tree_num: int):
    async with session_scope() as s:
        result = await s.execute(select(CommandTree).where(and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)))
        rec = result.scalar_one_or_none()
        if not rec:
            rec = CommandTree(chat_id=chat_id, tree_num=tree_num)
            s.add(rec)
            await s.commit()
        return rec

async def set_tree_enabled(chat_id: int, tree_num: int, enabled: bool) -> None:
    async with session_scope() as s:
        result = await s.execute(select(CommandTree).where(and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)))
        rec = result.scalar_one_or_none()
        if rec:
            rec.enabled = enabled
        else:
            s.add(CommandTree(chat_id=chat_id, tree_num=tree_num, enabled=enabled))
        await s.commit()

async def set_tree_min_role(chat_id: int, tree_num: int, min_role: int) -> None:
    async with session_scope() as s:
        result = await s.execute(select(CommandTree).where(and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)))
        rec = result.scalar_one_or_none()
        if rec:
            rec.min_role = min_role
        else:
            s.add(CommandTree(chat_id=chat_id, tree_num=tree_num, min_role=min_role))
        await s.commit()

async def get_checks(user_id: int) -> int:
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        return rec.checks if rec else 0

async def add_checks(user_id: int, amount: int) -> int:
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        if rec:
            rec.checks += amount
        else:
            rec = PremiumBalance(user_id=user_id, checks=amount)
            s.add(rec)
        await s.commit()
        return rec.checks

async def spend_checks(user_id: int, amount: int) -> bool:
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        if not rec or rec.checks < amount:
            return False
        rec.checks -= amount
        await s.commit()
        return True

async def get_shop_items(premium_only: bool = False):
    async with session_scope() as s:
        q = select(ShopItem).where(ShopItem.is_active == True)
        if premium_only:
            q = q.where(ShopItem.is_premium == True)
        result = await s.execute(q)
        return list(result.scalars().all())

async def get_shop_item(item_id: int):
    async with session_scope() as s:
        return await s.get(ShopItem, item_id)

async def buy_item(user_id: int, item_id: int) -> tuple[bool, str]:
    item = await get_shop_item(item_id)
    if not item or not item.is_active:
        return False, "Товар не найден."
    if item.price_checks > 0:
        ok = await spend_checks(user_id, item.price_checks)
        if not ok:
            return False, f"Недостаточно чатиков! Нужно {item.price_checks} 🎫"
    elif item.price_iris > 0:
        async with session_scope() as s:
            user = await s.get(User, user_id)
            if not user or user.balance < item.price_iris:
                return False, f"Недостаточно ирисок! Нужно {item.price_iris} 🍬"
            user.balance -= item.price_iris
            await s.commit()
    async with session_scope() as s:
        s.add(Purchase(user_id=user_id, item_id=item_id))
        await s.commit()
    return True, item.name

async def add_shop_item(name: str, description: str, price_iris: int, price_checks: int, is_premium: bool):
    async with session_scope() as s:
        item = ShopItem(name=name, description=description, price_iris=price_iris, price_checks=price_checks, is_premium=is_premium)
        s.add(item)
        await s.commit()
        return item

async def get_spam_entries(chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(SpamEntry).where(SpamEntry.chat_id == chat_id))
        return list(result.scalars().all())

async def add_spam_entry(chat_id: int, pattern: str, added_by: int):
    async with session_scope() as s:
        s.add(SpamEntry(chat_id=chat_id, pattern=pattern.lower(), added_by=added_by))
        await s.commit()

async def remove_spam_entry(chat_id: int, pattern: str) -> bool:
    async with session_scope() as s:
        result = await s.execute(select(SpamEntry).where(and_(SpamEntry.chat_id == chat_id, SpamEntry.pattern == pattern.lower())))
        entry = result.scalar_one_or_none()
        if not entry:
            return False
        await s.delete(entry)
        await s.commit()
        return True

# ─── База нарушителей ─────────────────────────────────────────────────────────

async def get_banlist() -> list:
    async with session_scope() as s:
        result = await s.execute(select(GlobalBanList))
        return list(result.scalars().all())

async def add_to_banlist(user_id: int, reason: str, added_by: int) -> bool:
    async with session_scope() as s:
        existing = await s.get(GlobalBanList, user_id)
        if existing:
            return False
        s.add(GlobalBanList(user_id=user_id, reason=reason, added_by=added_by))
        await s.commit()
        return True

async def remove_from_banlist(user_id: int) -> bool:
    async with session_scope() as s:
        entry = await s.get(GlobalBanList, user_id)
        if not entry:
            return False
        await s.delete(entry)
        await s.commit()
        return True

async def is_in_banlist(user_id: int) -> bool:
    async with session_scope() as s:
        return await s.get(GlobalBanList, user_id) is not None

# ─── Премиум-подписка ─────────────────────────────────────────────────────────

async def get_premium_record(user_id: int):
    async with session_scope() as s:
        return await s.get(PremiumBalance, user_id)

async def activate_premium(user_id: int) -> None:
    """Активирует премиум на 30 дней."""
    from datetime import timedelta
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        now = datetime.utcnow()
        if rec:
            # Продлеваем если уже есть
            base = rec.premium_until if rec.premium_until and rec.premium_until > now else now
            rec.has_premium = True
            rec.premium_until = base + timedelta(days=30)
        else:
            rec = PremiumBalance(
                user_id=user_id,
                checks=0,
                has_premium=True,
                premium_until=now + timedelta(days=30)
            )
            s.add(rec)
        await s.commit()

async def is_premium(user_id: int) -> bool:
    """Проверяет активен ли премиум."""
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        if not rec or not rec.has_premium:
            return False
        if rec.premium_until and rec.premium_until < datetime.utcnow():
            rec.has_premium = False
            await s.commit()
            return False
        return True

async def claim_free_chatik(user_id: int) -> tuple[bool, str]:
    """Выдаёт 1 бесплатный чатик в день для премиум-пользователей."""
    from datetime import timedelta
    async with session_scope() as s:
        rec = await s.get(PremiumBalance, user_id)
        if not rec or not rec.has_premium:
            return False, "no_premium"
        if rec.premium_until and rec.premium_until < datetime.utcnow():
            rec.has_premium = False
            await s.commit()
            return False, "expired"
        now = datetime.utcnow()
        if rec.last_free_chatik:
            diff = now - rec.last_free_chatik
            if diff.total_seconds() < 86400:
                remaining = 86400 - diff.total_seconds()
                h = int(remaining // 3600)
                m = int((remaining % 3600) // 60)
                return False, f"{h}ч {m}мин"
        rec.checks += 1
        rec.last_free_chatik = now
        await s.commit()
        return True, str(rec.checks)

# ─── Заметки ──────────────────────────────────────────────────────────────────

async def add_note(user_id: int, chat_id: int, name: str, content: str) -> None:
    async with session_scope() as s:
        existing = await s.execute(
            select(Note).where(and_(Note.user_id == user_id, Note.chat_id == chat_id, Note.name == name))
        )
        note = existing.scalar_one_or_none()
        if note:
            note.content = content
        else:
            s.add(Note(user_id=user_id, chat_id=chat_id, name=name, content=content))
        await s.commit()

async def get_note(user_id: int, chat_id: int, name: str):
    async with session_scope() as s:
        result = await s.execute(
            select(Note).where(and_(Note.user_id == user_id, Note.chat_id == chat_id, Note.name == name))
        )
        return result.scalar_one_or_none()

async def get_notes(user_id: int, chat_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(
            select(Note).where(and_(Note.user_id == user_id, Note.chat_id == chat_id))
        )
        return list(result.scalars().all())

async def delete_note(user_id: int, chat_id: int, name: str) -> bool:
    async with session_scope() as s:
        result = await s.execute(
            select(Note).where(and_(Note.user_id == user_id, Note.chat_id == chat_id, Note.name == name))
        )
        note = result.scalar_one_or_none()
        if not note:
            return False
        await s.delete(note)
        await s.commit()
        return True

async def edit_note(user_id: int, chat_id: int, name: str, content: str) -> bool:
    async with session_scope() as s:
        result = await s.execute(
            select(Note).where(and_(Note.user_id == user_id, Note.chat_id == chat_id, Note.name == name))
        )
        note = result.scalar_one_or_none()
        if not note:
            return False
        note.content = content
        await s.commit()
        return True

# ─── Неактивные пользователи ──────────────────────────────────────────────────

async def get_inactive_users(chat_id: int, since: datetime) -> list[int]:
    """Возвращает user_id тех, кто не писал в чате с даты since."""
    async with session_scope() as s:
        # Те кто ПИСАЛ после since
        active_result = await s.execute(
            select(DailyActivity.user_id).where(
                and_(DailyActivity.chat_id == chat_id, DailyActivity.date >= since)
            ).distinct()
        )
        active_ids = set(row[0] for row in active_result.fetchall())
        # Все кто вообще есть в этом чате
        all_result = await s.execute(
            select(DailyActivity.user_id).where(DailyActivity.chat_id == chat_id).distinct()
        )
        all_ids = set(row[0] for row in all_result.fetchall())
        return list(all_ids - active_ids)

# ══════════════════════════════════════════════════════════════════════════════
# НОВЫЕ ФУНКЦИИ CHATIX 2.0
# ══════════════════════════════════════════════════════════════════════════════

# ─── XP и уровни ─────────────────────────────────────────────────────────────

XP_PER_MESSAGE = 3
XP_PER_LEVEL = 100  # базовый XP для первого уровня, растёт

LEVEL_NAMES = {
    1: "🌱 Новичок", 2: "🌿 Участник", 3: "🌳 Активный", 4: "🌟 Опытный",
    5: "💫 Ветеран", 6: "🔥 Мастер", 7: "⚡ Эксперт", 8: "💎 Элита",
    9: "👑 Легенда", 10: "🌌 Бессмертный",
}

def xp_for_level(level: int) -> int:
    return XP_PER_LEVEL * level

async def add_xp(user_id: int, amount: int = XP_PER_MESSAGE) -> tuple[int, int, bool]:
    """Добавляет XP, возвращает (xp, level, leveled_up)."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return 0, 1, False
        user.xp += amount
        old_level = user.level
        while user.xp >= xp_for_level(user.level):
            user.xp -= xp_for_level(user.level)
            user.level += 1
        leveled_up = user.level > old_level
        await s.commit()
        return user.xp, user.level, leveled_up

async def get_level_info(user_id: int) -> tuple[int, int, int]:
    """Возвращает (level, xp, xp_needed)."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return 1, 0, xp_for_level(1)
        return user.level, user.xp, xp_for_level(user.level)

# ─── Стрики ───────────────────────────────────────────────────────────────────

async def update_streak(user_id: int) -> tuple[int, bool]:
    """Обновляет стрик, возвращает (streak, is_new_day)."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return 0, False
        now = datetime.utcnow()
        today = now.date()
        if user.last_streak_date:
            last = user.last_streak_date.date()
            if last == today:
                return user.streak, False
            elif (today - last).days == 1:
                user.streak += 1
            else:
                user.streak = 1
        else:
            user.streak = 1
        user.last_streak_date = now
        await s.commit()
        return user.streak, True

# ─── Ачивки ───────────────────────────────────────────────────────────────────

ACHIEVEMENTS = {
    "first_message":   {"name": "💬 Первое слово",     "desc": "Отправил первое сообщение"},
    "messages_100":    {"name": "📝 Болтун",           "desc": "100 сообщений"},
    "messages_1000":   {"name": "🗣️ Оратор",           "desc": "1000 сообщений"},
    "balance_1000":    {"name": "💰 Копилка",          "desc": "Накопил 1000 ирисок"},
    "balance_10000":   {"name": "🏦 Банкир",           "desc": "Накопил 10000 ирисок"},
    "casino_win":      {"name": "🎰 Удача",            "desc": "Выиграл в казино"},
    "casino_win_10":   {"name": "🎲 Игрок",            "desc": "Выиграл в казино 10 раз"},
    "level_5":         {"name": "⭐ Пятый уровень",    "desc": "Достиг 5 уровня"},
    "level_10":        {"name": "👑 Легенда",          "desc": "Достиг 10 уровня"},
    "streak_7":        {"name": "🔥 Неделя подряд",    "desc": "7 дней стрика"},
    "streak_30":       {"name": "🌟 Месяц подряд",     "desc": "30 дней стрика"},
    "married":         {"name": "💍 Женат/Замужем",    "desc": "Вступил в брак"},
    "clan_created":    {"name": "🏰 Основатель",       "desc": "Создал клан"},
    "rob_success":     {"name": "🦹 Грабитель",        "desc": "Успешно ограбил кого-то"},
    "auction_win":     {"name": "🔨 Аукционист",       "desc": "Выиграл аукцион"},
}

async def get_achievements(user_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(Achievement).where(Achievement.user_id == user_id))
        return list(result.scalars().all())

async def award_achievement(user_id: int, key: str) -> bool:
    """Выдаёт ачивку если её ещё нет. Возвращает True если новая."""
    async with session_scope() as s:
        result = await s.execute(select(Achievement).where(
            and_(Achievement.user_id == user_id, Achievement.key == key)
        ))
        if result.scalar_one_or_none():
            return False
        s.add(Achievement(user_id=user_id, key=key))
        await s.commit()
        return True

# ─── Квесты ───────────────────────────────────────────────────────────────────

QUEST_DEFINITIONS = {
    "messages_20":  {"desc": "Написать 20 сообщений",    "goal": 20,  "reward": 150},
    "casino_3":     {"desc": "Сыграть в казино 3 раза",  "goal": 3,   "reward": 200},
    "bonus_claim":  {"desc": "Получить ежедневный бонус","goal": 1,   "reward": 50},
    "rp_action":    {"desc": "Сделать РП-действие",      "goal": 1,   "reward": 75},
    "transfer":     {"desc": "Перевести ириски другому", "goal": 1,   "reward": 100},
}

async def get_today_quests(user_id: int, chat_id: int) -> list:
    async with session_scope() as s:
        today = datetime.utcnow().date()
        result = await s.execute(select(DailyQuest).where(and_(
            DailyQuest.user_id == user_id,
            DailyQuest.chat_id == chat_id,
            func.date(DailyQuest.date) == today,
        )))
        quests = list(result.scalars().all())
        if not quests:
            import random
            keys = random.sample(list(QUEST_DEFINITIONS.keys()), min(3, len(QUEST_DEFINITIONS)))
            for key in keys:
                qd = QUEST_DEFINITIONS[key]
                q = DailyQuest(user_id=user_id, chat_id=chat_id, quest_key=key,
                               goal=qd["goal"], reward=qd["reward"])
                s.add(q)
            await s.commit()
            result2 = await s.execute(select(DailyQuest).where(and_(
                DailyQuest.user_id == user_id,
                DailyQuest.chat_id == chat_id,
                func.date(DailyQuest.date) == today,
            )))
            quests = list(result2.scalars().all())
        return quests

async def progress_quest(user_id: int, chat_id: int, quest_key: str) -> tuple[bool, int]:
    """Двигает прогресс квеста. Возвращает (completed, reward)."""
    async with session_scope() as s:
        today = datetime.utcnow().date()
        result = await s.execute(select(DailyQuest).where(and_(
            DailyQuest.user_id == user_id,
            DailyQuest.chat_id == chat_id,
            DailyQuest.quest_key == quest_key,
            DailyQuest.completed == False,
            func.date(DailyQuest.date) == today,
        )))
        quest = result.scalar_one_or_none()
        if not quest:
            return False, 0
        quest.progress += 1
        if quest.progress >= quest.goal:
            quest.completed = True
            await s.commit()
            return True, quest.reward
        await s.commit()
        return False, 0

# ─── Банк ─────────────────────────────────────────────────────────────────────

async def deposit_bank(user_id: int, amount: int, days: int = 3) -> tuple[bool, str]:
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user or user.balance < amount:
            return False, "Недостаточно ирисок"
        rate = 5 if days <= 3 else 10 if days <= 7 else 15
        user.balance -= amount
        withdraw_at = datetime.utcnow() + timedelta(days=days)
        s.add(BankDeposit(user_id=user_id, amount=amount, withdraw_after=withdraw_at, rate=rate))
        await s.commit()
        return True, f"Вклад на {days} дн. под {rate}%"

async def get_deposits(user_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(BankDeposit).where(and_(
            BankDeposit.user_id == user_id, BankDeposit.withdrawn == False
        )))
        return list(result.scalars().all())

async def withdraw_deposit(user_id: int, deposit_id: int) -> tuple[bool, int]:
    async with session_scope() as s:
        dep = await s.get(BankDeposit, deposit_id)
        if not dep or dep.user_id != user_id or dep.withdrawn:
            return False, 0
        if datetime.utcnow() < dep.withdraw_after:
            return False, 0
        profit = int(dep.amount * dep.rate / 100)
        total = dep.amount + profit
        dep.withdrawn = True
        user = await s.get(User, user_id)
        if user:
            user.balance += total
        await s.commit()
        return True, total

# ─── Грабёж ───────────────────────────────────────────────────────────────────

async def rob_user(robber_id: int, target_id: int) -> tuple[bool, int, str]:
    """Попытка ограбления. Возвращает (success, amount, message)."""
    import random
    async with session_scope() as s:
        robber = await s.get(User, robber_id)
        target = await s.get(User, target_id)
        if not robber or not target:
            return False, 0, "Пользователь не найден"
        now = datetime.utcnow()
        if robber.last_rob and (now - robber.last_rob).total_seconds() < 3600:
            remaining = 3600 - (now - robber.last_rob).total_seconds()
            return False, 0, f"Перезарядка: {int(remaining//60)} мин."
        robber.last_rob = now
        if target.balance < 50:
            await s.commit()
            return False, 0, "У жертвы нет ирисок"
        if random.random() < 0.4:  # 40% успех
            stolen = random.randint(10, min(100, target.balance // 4))
            target.balance -= stolen
            robber.balance += stolen
            await s.commit()
            return True, stolen, ""
        else:
            fine = min(50, robber.balance)
            robber.balance -= fine
            await s.commit()
            return False, fine, "провал"

# ─── Работа ───────────────────────────────────────────────────────────────────

WORK_SCENARIOS = [
    ("👨‍💻 Написал код", 80, 200),
    ("🚚 Развёз посылки", 60, 150),
    ("🍕 Работал курьером", 70, 180),
    ("🎨 Нарисовал логотип", 100, 250),
    ("📱 Снял рилс", 50, 300),
    ("🔧 Починил что-то", 90, 170),
    ("📦 Разобрал склад", 60, 140),
    ("🎤 Выступил на ивенте", 120, 350),
]

async def do_work(user_id: int) -> tuple[bool, int, str]:
    """Работа с cooldown 4 часа."""
    import random
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return False, 0, ""
        now = datetime.utcnow()
        if user.last_work and (now - user.last_work).total_seconds() < 14400:
            remaining = 14400 - (now - user.last_work).total_seconds()
            h = int(remaining // 3600)
            m = int((remaining % 3600) // 60)
            return False, 0, f"{h}ч {m}мин"
        desc, min_earn, max_earn = random.choice(WORK_SCENARIOS)
        earned = random.randint(min_earn, max_earn)
        user.balance += earned
        user.last_work = now
        await s.commit()
        return True, earned, desc

# ─── Аукцион ─────────────────────────────────────────────────────────────────

async def create_auction(chat_id: int, seller_id: int, item_name: str, start_price: int, hours: int = 1):
    async with session_scope() as s:
        ends = datetime.utcnow() + timedelta(hours=hours)
        auction = Auction(chat_id=chat_id, seller_id=seller_id, item_name=item_name,
                          start_price=start_price, current_price=start_price, ends_at=ends)
        s.add(auction)
        await s.commit()
        await s.refresh(auction)
        return auction

async def bid_auction(auction_id: int, bidder_id: int, amount: int) -> tuple[bool, str]:
    async with session_scope() as s:
        auction = await s.get(Auction, auction_id)
        if not auction or auction.finished:
            return False, "Аукцион завершён"
        if datetime.utcnow() > auction.ends_at:
            auction.finished = True
            await s.commit()
            return False, "Аукцион истёк"
        if amount <= auction.current_price:
            return False, f"Ставка должна быть > {auction.current_price}"
        bidder = await s.get(User, bidder_id)
        if not bidder or bidder.balance < amount:
            return False, "Недостаточно ирисок"
        if auction.top_bidder_id:
            prev = await s.get(User, auction.top_bidder_id)
            if prev:
                prev.balance += auction.current_price
        bidder.balance -= amount
        auction.current_price = amount
        auction.top_bidder_id = bidder_id
        await s.commit()
        return True, ""

async def get_active_auctions(chat_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(Auction).where(and_(
            Auction.chat_id == chat_id,
            Auction.finished == False,
            Auction.ends_at > datetime.utcnow(),
        )))
        return list(result.scalars().all())

async def finish_auction(auction_id: int) -> tuple[int | None, str, int]:
    """Завершает аукцион. Возвращает (winner_id, item_name, price)."""
    async with session_scope() as s:
        auction = await s.get(Auction, auction_id)
        if not auction:
            return None, "", 0
        auction.finished = True
        await s.commit()
        return auction.top_bidder_id, auction.item_name, auction.current_price

# ─── Кланы ───────────────────────────────────────────────────────────────────

async def create_clan(chat_id: int, owner_id: int, name: str) -> tuple[bool, str]:
    async with session_scope() as s:
        existing = await s.execute(select(Clan).where(and_(Clan.chat_id == chat_id, Clan.name == name)))
        if existing.scalar_one_or_none():
            return False, "Клан с таким именем уже существует"
        user = await s.get(User, owner_id)
        if not user or user.balance < 500:
            return False, "Нужно 500 ирисок для создания клана"
        user.balance -= 500
        clan = Clan(chat_id=chat_id, owner_id=owner_id, name=name)
        s.add(clan)
        await s.flush()
        s.add(ClanMember(clan_id=clan.id, user_id=owner_id))
        await s.commit()
        return True, str(clan.id)

async def get_user_clan(user_id: int, chat_id: int):
    async with session_scope() as s:
        result = await s.execute(select(ClanMember).join(Clan).where(and_(
            ClanMember.user_id == user_id, Clan.chat_id == chat_id
        )))
        member = result.scalar_one_or_none()
        if not member:
            return None, None
        clan = await s.get(Clan, member.clan_id)
        return clan, member

async def get_clan_by_name(chat_id: int, name: str):
    async with session_scope() as s:
        result = await s.execute(select(Clan).where(and_(Clan.chat_id == chat_id, Clan.name == name)))
        return result.scalar_one_or_none()

async def get_clan_members(clan_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(ClanMember).where(ClanMember.clan_id == clan_id))
        return list(result.scalars().all())

async def join_clan(clan_id: int, user_id: int) -> tuple[bool, str]:
    async with session_scope() as s:
        clan = await s.get(Clan, clan_id)
        if not clan:
            return False, "Клан не найден"
        existing = await s.execute(select(ClanMember).where(ClanMember.user_id == user_id))
        if existing.scalar_one_or_none():
            return False, "Ты уже в клане"
        s.add(ClanMember(clan_id=clan_id, user_id=user_id))
        await s.commit()
        return True, ""

async def leave_clan(user_id: int, chat_id: int) -> bool:
    async with session_scope() as s:
        result = await s.execute(select(ClanMember).join(Clan).where(and_(
            ClanMember.user_id == user_id, Clan.chat_id == chat_id
        )))
        member = result.scalar_one_or_none()
        if not member:
            return False
        await s.delete(member)
        await s.commit()
        return True

async def get_all_clans(chat_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(Clan).where(Clan.chat_id == chat_id))
        return list(result.scalars().all())

# ─── Дружба ──────────────────────────────────────────────────────────────────

async def send_friend_request(from_id: int, to_id: int, chat_id: int) -> tuple[bool, str]:
    async with session_scope() as s:
        existing_friendship = await s.execute(select(Friendship).where(
            or_(
                and_(Friendship.user1_id == from_id, Friendship.user2_id == to_id),
                and_(Friendship.user1_id == to_id, Friendship.user2_id == from_id),
            )
        ))
        if existing_friendship.scalar_one_or_none():
            return False, "Вы уже друзья"
        existing_req = await s.execute(select(FriendRequest).where(and_(
            FriendRequest.from_id == from_id, FriendRequest.to_id == to_id
        )))
        if existing_req.scalar_one_or_none():
            return False, "Запрос уже отправлен"
        s.add(FriendRequest(from_id=from_id, to_id=to_id, chat_id=chat_id))
        await s.commit()
        return True, ""

async def accept_friend(from_id: int, to_id: int) -> bool:
    async with session_scope() as s:
        result = await s.execute(select(FriendRequest).where(and_(
            FriendRequest.from_id == from_id, FriendRequest.to_id == to_id
        )))
        req = result.scalar_one_or_none()
        if not req:
            return False
        await s.delete(req)
        s.add(Friendship(user1_id=from_id, user2_id=to_id))
        await s.commit()
        return True

async def get_friends(user_id: int) -> list[int]:
    async with session_scope() as s:
        result = await s.execute(select(Friendship).where(
            or_(Friendship.user1_id == user_id, Friendship.user2_id == user_id)
        ))
        friends = []
        for f in result.scalars().all():
            friends.append(f.user2_id if f.user1_id == user_id else f.user1_id)
        return friends

async def get_pending_requests(user_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(FriendRequest).where(FriendRequest.to_id == user_id))
        return list(result.scalars().all())

# ─── Тикеты ───────────────────────────────────────────────────────────────────

async def create_ticket(chat_id: int, reporter_id: int, target_id: int, message_text: str, reason: str):
    async with session_scope() as s:
        ticket = Ticket(chat_id=chat_id, reporter_id=reporter_id,
                        target_id=target_id, message_text=message_text, reason=reason)
        s.add(ticket)
        await s.commit()
        await s.refresh(ticket)
        return ticket

async def get_open_tickets(chat_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(Ticket).where(and_(
            Ticket.chat_id == chat_id, Ticket.resolved == False
        )))
        return list(result.scalars().all())

async def resolve_ticket(ticket_id: int) -> bool:
    async with session_scope() as s:
        ticket = await s.get(Ticket, ticket_id)
        if not ticket:
            return False
        ticket.resolved = True
        await s.commit()
        return True

# ─── Инвентарь ────────────────────────────────────────────────────────────────

async def add_to_inventory(user_id: int, item_id: int) -> None:
    async with session_scope() as s:
        existing = await s.execute(select(Inventory).where(and_(
            Inventory.user_id == user_id, Inventory.item_id == item_id
        )))
        inv = existing.scalar_one_or_none()
        if inv:
            inv.quantity += 1
        else:
            s.add(Inventory(user_id=user_id, item_id=item_id))
        await s.commit()

async def get_inventory(user_id: int) -> list:
    async with session_scope() as s:
        result = await s.execute(select(Inventory).where(Inventory.user_id == user_id))
        return list(result.scalars().all())

# ─── Подарки ──────────────────────────────────────────────────────────────────

async def send_gift(from_id: int, to_id: int, item_id: int) -> tuple[bool, str]:
    async with session_scope() as s:
        existing = await s.execute(select(Inventory).where(and_(
            Inventory.user_id == from_id, Inventory.item_id == item_id
        )))
        inv = existing.scalar_one_or_none()
        if not inv or inv.quantity < 1:
            return False, "Этого предмета нет в инвентаре"
        inv.quantity -= 1
        if inv.quantity == 0:
            await s.delete(inv)
        s.add(Gift(from_id=from_id, to_id=to_id, item_id=item_id))
        to_inv = await s.execute(select(Inventory).where(and_(
            Inventory.user_id == to_id, Inventory.item_id == item_id
        )))
        to_inv_rec = to_inv.scalar_one_or_none()
        if to_inv_rec:
            to_inv_rec.quantity += 1
        else:
            s.add(Inventory(user_id=to_id, item_id=item_id))
        await s.commit()
        return True, ""

# ─── Лог-канал ────────────────────────────────────────────────────────────────

async def set_log_chat(chat_id: int, log_chat_id: int) -> None:
    await update_chat_settings(chat_id, log_chat_id=log_chat_id)

async def get_log_chat(chat_id: int) -> int | None:
    cs = await get_chat_settings(chat_id)
    return cs.log_chat_id if cs else None

# ─── Медленный режим ─────────────────────────────────────────────────────────

async def set_slow_mode(chat_id: int, seconds: int) -> None:
    await update_chat_settings(chat_id, slow_mode_seconds=seconds)

async def check_slow_mode(user_id: int, chat_id: int, cooldown: int) -> tuple[bool, int]:
    """True если можно писать, False + секунды если нет."""
    async with session_scope() as s:
        result = await s.execute(select(SlowModeTracker).where(and_(
            SlowModeTracker.user_id == user_id,
            SlowModeTracker.chat_id == chat_id,
        )))
        tracker = result.scalar_one_or_none()
        now = datetime.utcnow()
        if tracker:
            elapsed = (now - tracker.last_message).total_seconds()
            if elapsed < cooldown:
                return False, int(cooldown - elapsed)
            tracker.last_message = now
        else:
            s.add(SlowModeTracker(user_id=user_id, chat_id=chat_id, last_message=now))
        await s.commit()
        return True, 0

# ─── Статистика чата ─────────────────────────────────────────────────────────

async def get_chat_stats(chat_id: int) -> dict:
    async with session_scope() as s:
        week_ago = datetime.utcnow() - timedelta(days=7)
        result = await s.execute(select(
            func.sum(DailyActivity.messages),
            func.count(func.distinct(DailyActivity.user_id))
        ).where(and_(
            DailyActivity.chat_id == chat_id,
            DailyActivity.date >= week_ago,
        )))
        row = result.one()
        total_msgs = row[0] or 0
        unique_users = row[1] or 0
        by_day_result = await s.execute(
            select(func.date(DailyActivity.date), func.sum(DailyActivity.messages))
            .where(and_(DailyActivity.chat_id == chat_id, DailyActivity.date >= week_ago))
            .group_by(func.date(DailyActivity.date))
            .order_by(func.date(DailyActivity.date))
        )
        by_day = [(str(row[0]), int(row[1])) for row in by_day_result.all()]
        return {"total_messages": total_msgs, "unique_users": unique_users, "by_day": by_day}
