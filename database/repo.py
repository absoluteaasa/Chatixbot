"""
Репозиторий Chatix — все CRUD операции
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
}

def session_scope():
    return async_session()

# ─── Пользователи ─────────────────────────────────────────────────────────────

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

# ─── Варны ────────────────────────────────────────────────────────────────────

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

# ─── Репутация ────────────────────────────────────────────────────────────────

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

# ─── Топ ──────────────────────────────────────────────────────────────────────

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

# ─── Браки ────────────────────────────────────────────────────────────────────

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

# ─── Настройки чата ───────────────────────────────────────────────────────────

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

# ─── Профиль ──────────────────────────────────────────────────────────────────

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

# ─── Активность ───────────────────────────────────────────────────────────────

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

# ─── Должности ────────────────────────────────────────────────────────────────

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

# ─── Деревья команд ───────────────────────────────────────────────────────────

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

# ─── Премиум (чеки) ───────────────────────────────────────────────────────────

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

# ─── Магазин ──────────────────────────────────────────────────────────────────

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
            return False, f"Недостаточно чеков! Нужно {item.price_checks} 🎫"
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

# ─── Спамбаза ─────────────────────────────────────────────────────────────────

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
