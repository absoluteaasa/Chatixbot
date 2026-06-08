"""
Репозиторий — все CRUD-операции с БД.
Используется из хэндлеров, чтобы не смешивать логику с работой с БД.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.db import (
    ChatSettings, Marriage, ReputationVote,
    Transfer, User, Warning, async_session,
)

logger = logging.getLogger(__name__)


# ─── Вспомогательная функция сессии ──────────────────────────────────────────

def session_scope():
    return async_session()


# ─── Пользователи ─────────────────────────────────────────────────────────────

async def get_or_create_user(user_id: int, username: str | None, full_name: str) -> User:
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            user = User(id=user_id, username=username, full_name=full_name)
            s.add(user)
            await s.commit()
            await s.refresh(user)
            logger.info(f"Создан новый пользователь: {user_id} ({full_name})")
        else:
            # Обновляем имя при необходимости
            if user.full_name != full_name or user.username != username:
                user.full_name = full_name
                user.username = username
                await s.commit()
        return user


async def get_user(user_id: int) -> User | None:
    async with session_scope() as s:
        return await s.get(User, user_id)


async def update_balance(user_id: int, delta: int) -> int:
    """Изменяет баланс на delta (может быть отрицательным). Возвращает новый баланс."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return 0
        user.balance = max(0, user.balance + delta)
        await s.commit()
        return user.balance


async def increment_messages(user_id: int) -> None:
    async with session_scope() as s:
        await s.execute(
            update(User).where(User.id == user_id).values(
                messages_count=User.messages_count + 1
            )
        )
        await s.commit()


# ─── Бонус ────────────────────────────────────────────────────────────────────

async def claim_daily_bonus(user_id: int, amount: int) -> tuple[bool, datetime | None]:
    """Возвращает (успех, время_следующего_бонуса)."""
    async with session_scope() as s:
        user = await s.get(User, user_id)
        if not user:
            return False, None

        now = datetime.utcnow()
        if user.last_bonus and (now - user.last_bonus) < timedelta(hours=24):
            next_bonus = user.last_bonus + timedelta(hours=24)
            return False, next_bonus

        user.balance += amount
        user.last_bonus = now
        await s.commit()
        return True, now + timedelta(hours=24)


# ─── Переводы ─────────────────────────────────────────────────────────────────

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
    """Добавляет варн и возвращает общее количество варнов."""
    async with session_scope() as s:
        s.add(Warning(user_id=user_id, chat_id=chat_id, reason=reason, issued_by=issued_by))
        user = await s.get(User, user_id)
        if user:
            user.warnings += 1
        await s.commit()
        return user.warnings if user else 1


async def get_warnings(user_id: int, chat_id: int) -> list[Warning]:
    async with session_scope() as s:
        result = await s.execute(
            select(Warning).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        return list(result.scalars().all())


async def clear_warnings(user_id: int, chat_id: int) -> None:
    async with session_scope() as s:
        await s.execute(
            delete(Warning).where(
                and_(Warning.user_id == user_id, Warning.chat_id == chat_id)
            )
        )
        user = await s.get(User, user_id)
        if user:
            user.warnings = 0
        await s.commit()


# ─── Репутация ────────────────────────────────────────────────────────────────

async def vote_reputation(voter_id: int, target_id: int, chat_id: int, value: int) -> tuple[bool, str]:
    """
    Голосует за/против репутации.
    Возвращает (успех, сообщение_об_ошибке).
    """
    async with session_scope() as s:
        # Проверяем, голосовал ли уже сегодня
        today = datetime.utcnow().date()
        existing = await s.execute(
            select(ReputationVote).where(
                and_(
                    ReputationVote.voter_id == voter_id,
                    ReputationVote.target_id == target_id,
                    ReputationVote.chat_id == chat_id,
                    func.date(ReputationVote.created_at) == today,
                )
            )
        )
        if existing.scalar():
            return False, "Ты уже голосовал за этого пользователя сегодня!"

        s.add(ReputationVote(voter_id=voter_id, target_id=target_id, chat_id=chat_id, value=value))
        user = await s.get(User, target_id)
        if user:
            user.reputation += value
        await s.commit()
        return True, ""


# ─── Топ ──────────────────────────────────────────────────────────────────────

async def get_top_users(limit: int = 10) -> dict[str, list[User]]:
    async with session_scope() as s:
        rich = (await s.execute(
            select(User).order_by(User.balance.desc()).limit(limit)
        )).scalars().all()

        active = (await s.execute(
            select(User).order_by(User.messages_count.desc()).limit(limit)
        )).scalars().all()

        reputable = (await s.execute(
            select(User).order_by(User.reputation.desc()).limit(limit)
        )).scalars().all()

        return {"rich": list(rich), "active": list(active), "reputable": list(reputable)}


# ─── Браки ────────────────────────────────────────────────────────────────────

async def get_marriage(user_id: int, chat_id: int) -> Marriage | None:
    async with session_scope() as s:
        result = await s.execute(
            select(Marriage).where(
                and_(
                    or_(Marriage.user1_id == user_id, Marriage.user2_id == user_id),
                    Marriage.chat_id == chat_id,
                )
            )
        )
        return result.scalar_one_or_none()


async def create_marriage(user1_id: int, user2_id: int, chat_id: int) -> Marriage:
    async with session_scope() as s:
        marriage = Marriage(user1_id=user1_id, user2_id=user2_id, chat_id=chat_id)
        s.add(marriage)
        await s.commit()
        await s.refresh(marriage)
        return marriage


async def divorce(user_id: int, chat_id: int) -> bool:
    async with session_scope() as s:
        result = await s.execute(
            select(Marriage).where(
                and_(
                    or_(Marriage.user1_id == user_id, Marriage.user2_id == user_id),
                    Marriage.chat_id == chat_id,
                )
            )
        )
        marriage = result.scalar_one_or_none()
        if not marriage:
            return False
        await s.delete(marriage)
        await s.commit()
        return True


async def get_all_marriages(chat_id: int) -> list[Marriage]:
    async with session_scope() as s:
        result = await s.execute(
            select(Marriage).where(Marriage.chat_id == chat_id)
        )
        return list(result.scalars().all())


# ─── Настройки чата ───────────────────────────────────────────────────────────

async def get_chat_settings(chat_id: int) -> ChatSettings:
    async with session_scope() as s:
        settings = await s.get(ChatSettings, chat_id)
        if not settings:
            settings = ChatSettings(chat_id=chat_id)
            s.add(settings)
            await s.commit()
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
    from database.db import UserProfile
    async with session_scope() as s:
        p = await s.get(UserProfile, user_id)
        if not p:
            p = UserProfile(user_id=user_id)
            s.add(p)
            await s.commit()
        return p


async def update_profile(user_id: int, **kwargs) -> None:
    from database.db import UserProfile
    from datetime import datetime
    async with session_scope() as s:
        p = await s.get(UserProfile, user_id)
        if not p:
            p = UserProfile(user_id=user_id)
            s.add(p)
        for k, v in kwargs.items():
            setattr(p, k, v)
        p.updated_at = datetime.utcnow()
        await s.commit()


# ─── Активность по дням ───────────────────────────────────────────────────────

async def record_daily_activity(user_id: int, chat_id: int) -> None:
    from database.db import DailyActivity
    from sqlalchemy import and_, func
    from datetime import datetime, date
    async with session_scope() as s:
        today = datetime.utcnow().date()
        result = await s.execute(
            select(DailyActivity).where(
                and_(
                    DailyActivity.user_id == user_id,
                    DailyActivity.chat_id == chat_id,
                    func.date(DailyActivity.date) == today,
                )
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.messages += 1
        else:
            s.add(DailyActivity(user_id=user_id, chat_id=chat_id,
                                date=datetime.utcnow(), messages=1))
        await s.commit()


async def get_activity_last_days(user_id: int, chat_id: int, days: int = 7):
    from database.db import DailyActivity
    from sqlalchemy import and_, func
    from datetime import datetime, timedelta
    async with session_scope() as s:
        since = datetime.utcnow() - timedelta(days=days)
        result = await s.execute(
            select(DailyActivity).where(
                and_(
                    DailyActivity.user_id == user_id,
                    DailyActivity.chat_id == chat_id,
                    DailyActivity.date >= since,
                )
            ).order_by(DailyActivity.date)
        )
        return list(result.scalars().all())


async def get_last_activity(user_id: int, chat_id: int):
    from database.db import DailyActivity
    from sqlalchemy import and_
    async with session_scope() as s:
        result = await s.execute(
            select(DailyActivity).where(
                and_(
                    DailyActivity.user_id == user_id,
                    DailyActivity.chat_id == chat_id,
                )
            ).order_by(DailyActivity.date.desc()).limit(1)
        )
        return result.scalar_one_or_none()


# ─── Должности ────────────────────────────────────────────────────────────────

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
    2: "Экономика",
    3: "Браки",
    4: "Репутация",
    5: "РП-команды",
    6: "Профиль",
}


async def get_user_role(user_id: int, chat_id: int) -> int:
    from database.db import UserRole
    async with session_scope() as s:
        result = await s.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.chat_id == chat_id)
            )
        )
        rec = result.scalar_one_or_none()
        return rec.role if rec else 0


async def set_user_role(user_id: int, chat_id: int, role: int) -> None:
    from database.db import UserRole
    async with session_scope() as s:
        result = await s.execute(
            select(UserRole).where(
                and_(UserRole.user_id == user_id, UserRole.chat_id == chat_id)
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.role = role
        else:
            s.add(UserRole(user_id=user_id, chat_id=chat_id, role=role))
        await s.commit()


async def get_all_roles(chat_id: int) -> list:
    from database.db import UserRole
    async with session_scope() as s:
        result = await s.execute(
            select(UserRole).where(
                and_(UserRole.chat_id == chat_id, UserRole.role > 0)
            ).order_by(UserRole.role.desc())
        )
        return list(result.scalars().all())


# ─── Деревья команд ───────────────────────────────────────────────────────────

async def get_tree(chat_id: int, tree_num: int):
    from database.db import CommandTree
    async with session_scope() as s:
        result = await s.execute(
            select(CommandTree).where(
                and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)
            )
        )
        rec = result.scalar_one_or_none()
        if not rec:
            rec = CommandTree(chat_id=chat_id, tree_num=tree_num)
            s.add(rec)
            await s.commit()
        return rec


async def set_tree_enabled(chat_id: int, tree_num: int, enabled: bool) -> None:
    from database.db import CommandTree
    async with session_scope() as s:
        result = await s.execute(
            select(CommandTree).where(
                and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.enabled = enabled
        else:
            s.add(CommandTree(chat_id=chat_id, tree_num=tree_num, enabled=enabled))
        await s.commit()


async def set_tree_min_role(chat_id: int, tree_num: int, min_role: int) -> None:
    from database.db import CommandTree
    async with session_scope() as s:
        result = await s.execute(
            select(CommandTree).where(
                and_(CommandTree.chat_id == chat_id, CommandTree.tree_num == tree_num)
            )
        )
        rec = result.scalar_one_or_none()
        if rec:
            rec.min_role = min_role
        else:
            s.add(CommandTree(chat_id=chat_id, tree_num=tree_num, min_role=min_role))
        await s.commit()
