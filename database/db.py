"""
Модели БД Chatix
"""
from __future__ import annotations
import logging
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from config import settings

logger = logging.getLogger(__name__)
engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64))
    full_name: Mapped[str] = mapped_column(String(128), default="")
    balance: Mapped[int] = mapped_column(Integer, default=50)
    reputation: Mapped[int] = mapped_column(Integer, default=0)
    warnings: Mapped[int] = mapped_column(Integer, default=0)
    messages_count: Mapped[int] = mapped_column(Integer, default=0)
    last_bonus: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Transfer(Base):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    receiver_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    amount: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Marriage(Base):
    __tablename__ = "marriages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    user2_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Warning(Base):
    __tablename__ = "warnings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    chat_id: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(Text, default="Нет причины")
    issued_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ChatSettings(Base):
    __tablename__ = "chat_settings"
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)
    forbidden_words: Mapped[str] = mapped_column(Text, default="")
    block_links: Mapped[bool] = mapped_column(Boolean, default=False)
    antiflood: Mapped[bool] = mapped_column(Boolean, default=True)

class ReputationVote(Base):
    __tablename__ = "reputation_votes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    voter_id: Mapped[int] = mapped_column(BigInteger)
    target_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    value: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UserProfile(Base):
    __tablename__ = "user_profiles"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    age: Mapped[str | None] = mapped_column(String(16), nullable=True)
    city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    hobby: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class DailyActivity(Base):
    __tablename__ = "daily_activity"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[datetime] = mapped_column(DateTime)
    messages: Mapped[int] = mapped_column(Integer, default=0)

class UserRole(Base):
    __tablename__ = "user_roles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    role: Mapped[int] = mapped_column(Integer, default=0)

class CommandTree(Base):
    __tablename__ = "command_trees"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    tree_num: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    min_role: Mapped[int] = mapped_column(Integer, default=0)

class PremiumBalance(Base):
    __tablename__ = "premium_balance"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    checks: Mapped[int] = mapped_column(Integer, default=0)
    # Премиум-подписка (True если активна)
    has_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    premium_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_free_chatik: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class ShopItem(Base):
    __tablename__ = "shop_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, default="")
    price_iris: Mapped[int] = mapped_column(Integer, default=0)
    price_checks: Mapped[int] = mapped_column(Integer, default=0)
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("shop_items.id"))
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SpamEntry(Base):
    __tablename__ = "spam_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    pattern: Mapped[str] = mapped_column(Text)
    added_by: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    chat_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
