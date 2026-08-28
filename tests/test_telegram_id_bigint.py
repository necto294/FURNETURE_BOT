"""Регрессия: telegram_id хранит произвольный 64-битный ID Telegram.

Баг: users.telegram_id был INTEGER (32 бита) в PostgreSQL, и любой большой
ID (например 5867235263) падал с NumericValueOutOfRange на /start.
SQLite-тесты этого не ловят (динамическая типизация), поэтому регрессия
гоняется на реальном PostgreSQL на изолированной throwaway-базе.

Если PostgreSQL недоступен или POSTGRES_* не настроены в .env, тесты
пропускаются — это не провал, а отсутствие окружения.
"""
import os
import sys
import unittest

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import engine as engine_mod
from database.engine import Base
from settings.config import ConfigBot

UUID_LIKE = 5867235263
SCRATCH_DB = "furniture_test_tgid"


def _postgres_available() -> bool:
    try:
        admin_url = make_url(ConfigBot.DATABASE_URL).set(database="postgres")
        admin_engine = create_engine(admin_url)
        with admin_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        admin_engine.dispose()
        return True
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_postgres_available(), "PostgreSQL недоступен")
class TelegramIdBigintTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        admin_url = make_url(ConfigBot.DATABASE_URL).set(database="postgres")
        self._admin_engine = create_engine(admin_url)
        with self._admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
            connection.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))

        scratch_url = make_url(ConfigBot.DATABASE_URL).set(database=SCRATCH_DB)
        self.engine = create_async_engine(scratch_url)
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = engine_mod.AsyncSessionLocal
        engine_mod.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        engine_mod.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        with self._admin_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"'))
        self._admin_engine.dispose()

    async def test_large_telegram_id_is_stored_and_found(self) -> None:
        from database import crud_catalog

        user = await crud_catalog.upsert_user(
            telegram_id=UUID_LIKE,
            username="largedebugharness",
            first_name="Большой",
        )
        self.assertEqual(user.telegram_id, UUID_LIKE)

        found = await crud_catalog.get_user_by_telegram_id(UUID_LIKE)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, user.id)
        self.assertEqual(found.telegram_id, UUID_LIKE)

    async def test_max_int64_boundary_is_stored(self) -> None:
        from database import crud_catalog

        max_id = 2**63 - 1
        user = await crud_catalog.upsert_user(telegram_id=max_id, username=None)
        self.assertEqual(user.telegram_id, max_id)


if __name__ == "__main__":
    unittest.main()
