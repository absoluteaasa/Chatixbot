"""
Конфигурация Chatix
"""
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = "YOUR_BOT_TOKEN_HERE"
    DATABASE_URL: str = "sqlite+aiosqlite:///chatix.db"
    ADMIN_ID: int = 0  # ID владельца бота для покупки чеков

    # Экономика
    DAILY_BONUS: int = 100
    STARTING_BALANCE: int = 50
    MARRIAGE_COST: int = 200

    # Антиспам
    MAX_WARNINGS: int = 3
    DEFAULT_MUTE_MINUTES: int = 10

    FORBIDDEN_WORDS: list[str] = []

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
