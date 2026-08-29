from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from settings.config import ConfigBot

# URL собирается в settings/config из DATABASE_PATH (.env): SQLite-файл,
# доступный через aiosqlite и боту, и синхронному Alembic (ADR 0004).
DATABASE_URL = ConfigBot.DATABASE_URL


async_engine = create_async_engine(DATABASE_URL, echo=True)
# Фабрика сессий не завершает объекты после фиксации транзакции.
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


# Базовый класс для всех моделей SQLAlchemy.
class Base(AsyncAttrs, DeclarativeBase):
    pass
