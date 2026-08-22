import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from database import crud
from database.engine import Base
from database.models import User


class UpsertUserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        # mkstemp не открывает файловый объект, поэтому контекст-менеджер не нужен.
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = crud.AsyncSessionLocal
        crud.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        crud.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)

    async def test_creates_user_without_admin_flag(self) -> None:
        user = await crud.upsert_user(
            telegram_id=1001,
            username="alice",
            first_name="Алиса",
            last_name="Иванова",
        )
        self.assertEqual(user.telegram_id, 1001)
        self.assertEqual(user.username, "alice")
        self.assertEqual(user.first_name, "Алиса")
        self.assertFalse(user.is_admin)

        stored = await crud.get_user_by_telegram_id(1001)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.id, user.id)

    async def test_updates_profile_and_keeps_admin(self) -> None:
        created = await crud.upsert_user(
            telegram_id=1002,
            username="bob",
            first_name="Боб",
            last_name=None,
        )
        async with self.session_factory() as session:
            db_user = await session.get(User, created.id)
            db_user.is_admin = True
            await session.commit()

        updated = await crud.upsert_user(
            telegram_id=1002,
            username="bob_new",
            first_name="Роберт",
            last_name="Петров",
        )
        self.assertEqual(updated.id, created.id)
        self.assertEqual(updated.username, "bob_new")
        self.assertEqual(updated.first_name, "Роберт")
        self.assertEqual(updated.last_name, "Петров")
        self.assertTrue(updated.is_admin)

    async def test_allows_users_without_username(self) -> None:
        first = await crud.upsert_user(telegram_id=2001, username=None, first_name="A")
        second = await crud.upsert_user(telegram_id=2002, username=None, first_name="B")
        self.assertNotEqual(first.id, second.id)


class StartHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_registers_telegram_user(self) -> None:
        os.environ.setdefault("BOT_TOKEN", "test-token")
        from handlers.backend.user.router import start_handler

        message = SimpleNamespace(
            from_user=SimpleNamespace(
                id=4242,
                username="visitor",
                first_name="Гость",
                last_name="Тестов",
            ),
            answer=AsyncMock(),
        )

        with (
            patch(
                "handlers.backend.user.router.upsert_user", new_callable=AsyncMock
            ) as upsert,
            patch(
                "handlers.backend.user.router.get_categories", new_callable=AsyncMock
            ) as categories,
            patch("handlers.backend.user.router.main_menu", return_value="menu"),
        ):
            categories.return_value = []
            await start_handler(message)

        upsert.assert_awaited_once_with(
            telegram_id=4242,
            username="visitor",
            first_name="Гость",
            last_name="Тестов",
        )
        message.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
