from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from settings.config import ConfigBot

# URL собирается из разложенных переменных .env (ADR 0002):
# PostgreSQL в Docker Compose, бот подключается через localhost.
DATABASE_URL = ConfigBot.DATABASE_URL


async_engine = create_async_engine(DATABASE_URL, echo=True)
# Фабрика сессий не завершает объекты после фиксации транзакции.
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


# Базовый класс для всех моделей SQLAlchemy.
class Base(AsyncAttrs, DeclarativeBase):
    pass
