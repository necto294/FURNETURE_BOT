import os

from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Определяем корневую папку проекта и путь к файлу базы данных.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "database", "database.db")


# Формируем адрес асинхронного подключения к SQLite.
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"


async_engine = create_async_engine(DATABASE_URL, echo=True)
# Фабрика сессий не завершает объекты после фиксации транзакции.
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


# Базовый класс для всех моделей SQLAlchemy.
class Base(AsyncAttrs, DeclarativeBase):
    pass
