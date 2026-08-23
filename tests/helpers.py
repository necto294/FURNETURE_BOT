"""Общие помощники для тестов админ-панели.

Импорт этого модуля обязан идти раньше импортов database/handlers:
здесь выставляется BOT_TOKEN и путь до корня проекта.
"""
import os
import sys
import tempfile
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")


from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import engine
from database.engine import Base


def make_state(data: dict | None = None) -> AsyncMock:
    # Заглушка FSMContext с готовыми данными для сценариев админки.
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


class _AnyMessageMeta(type):
    # Заставляем isinstance(x, _AnyMessage) всегда возвращать True.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


class _AnyCallbackQueryMeta(type):
    # Аналог _AnyMessage для CallbackQuery.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyCallbackQuery(metaclass=_AnyCallbackQueryMeta):
    """Заменяет CallbackQuery в isinstance-проверках."""


def patch_admin_message() -> Any:
    # Хендлеры разнесены по модулям, каждый импортирует Message отдельно.
    stack = ExitStack()
    for module in ("router", "categories", "furniture", "furniture_delete", "subcategories"):
        stack.enter_context(patch(f"handlers.admin.{module}.Message", _AnyMessage))
    return stack


def make_admin_event(data: str = "adm:menu", with_bot: bool = False) -> SimpleNamespace:
    message = SimpleNamespace(
        edit_text=AsyncMock(),
        answer=AsyncMock(),
        delete=AsyncMock(),
    )
    if with_bot:
        message.bot = SimpleNamespace(send_message=AsyncMock())
    return SimpleNamespace(
        message=message,
        data=data,
        from_user=SimpleNamespace(
            id=777,
            username="boss",
            first_name="Ольга",
            last_name="Админова",
        ),
        answer=AsyncMock(),
    )


class TempDbMixin:
    """Временная SQLite-база на время теста.

    mkstemp не открывает файловый объект, поэтому контекст-менеджер не нужен.
    Фабрику сессий подменяем в database.engine — единой точке патча для
    обеих половин CRUD.
    """

    async def asyncSetUp(self) -> None:
        descriptor, path = tempfile.mkstemp(suffix=".db")
        os.close(descriptor)
        self._tmp_path = path
        self.engine = create_async_engine(f"sqlite+aiosqlite:///{self._tmp_path}")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session_factory = async_sessionmaker(
            bind=self.engine, expire_on_commit=False
        )
        self._original_session = engine.AsyncSessionLocal
        engine.AsyncSessionLocal = self.session_factory

    async def asyncTearDown(self) -> None:
        engine.AsyncSessionLocal = self._original_session
        await self.engine.dispose()
        os.unlink(self._tmp_path)


__all__ = [
    "TempDbMixin",
    "_AnyCallbackQuery",
    "_AnyMessage",
    "make_admin_event",
    "make_state",
    "patch_admin_message",
]
