"""
Конфигурация бота — читается из переменных окружения или .env файла
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = "8677704219:AAEmBtVWhZa4yTmbGYK3VSdPLTGK62-icp4"
    DATABASE_URL: str = "sqlite+aiosqlite:///iris_bot.db"
    # Для PostgreSQL:
    # DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost/iris_bot"

    # Экономика
    DAILY_BONUS: int = 100          # Ириски за ежедневный бонус
    STARTING_BALANCE: int = 50      # Стартовый баланс
    MARRIAGE_COST: int = 200        # Стоимость брака

    # Антиспам
    MAX_WARNINGS: int = 3           # Варны до автобана
    DEFAULT_MUTE_MINUTES: int = 10

    # Фильтры
    FORBIDDEN_WORDS: list[str] = ["спам", "реклама"]  # Дефолтные запрещённые слова

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
