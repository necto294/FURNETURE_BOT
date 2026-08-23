"""Тесты шва авторизации админ-панели: middleware в handlers.admin.access."""
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import helpers

from handlers.admin.router import admin_menu_command

ADMIN_USER = SimpleNamespace(id="uuid-1", telegram_id=777, is_admin=True)
REGULAR_USER = None


class AdminAccessTests(unittest.IsolatedAsyncioTestCase):
    """Проверки шва авторизации: middleware в handlers.admin.access."""

    async def test_message_denied_for_regular_user(self) -> None:
        from handlers.admin.access import admin_guard

        message = SimpleNamespace(
            from_user=SimpleNamespace(id=1111, username="guest"),
            answer=AsyncMock(),
        )
        handler = AsyncMock(return_value="passed")

        with patch(
            "handlers.admin.access.get_user_by_telegram_id",
            new_callable=AsyncMock,
            return_value=REGULAR_USER,
        ):
            result = await admin_guard(handler, message, {})

        self.assertIsNone(result)
        handler.assert_not_awaited()
        message.answer.assert_awaited_once()
        self.assertIn("администратор", message.answer.await_args.args[0])

    async def test_callback_denied_without_admin_flag(self) -> None:
        from handlers.admin.access import admin_guard

        callback = helpers.make_admin_event("adm:addcat")
        handler = AsyncMock()

        with (
            patch(
                "handlers.admin.access.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=REGULAR_USER,
            ),
            # SimpleNamespace не проходит isinstance(event, CallbackQuery),
            # поэтому подменяем класс в модуле access (трюк как с Message).
            patch("handlers.admin.access.CallbackQuery", helpers._AnyCallbackQuery),
        ):
            await admin_guard(handler, callback, {})

        handler.assert_not_awaited()
        callback.answer.assert_awaited_once()
        self.assertTrue(callback.answer.await_args.kwargs.get("show_alert"))

    async def test_db_admin_passes_through(self) -> None:
        # Админ по флагу is_admin в базе проходит дальше без ответа.
        from handlers.admin.access import admin_guard

        event = helpers.make_admin_event("adm:addcat")
        handler = AsyncMock(return_value="passed")

        with patch(
            "handlers.admin.access.get_user_by_telegram_id",
            new_callable=AsyncMock,
            return_value=ADMIN_USER,
        ):
            result = await admin_guard(handler, event, {})

        self.assertEqual(result, "passed")
        handler.assert_awaited_once_with(event, {})
        event.answer.assert_not_awaited()

    async def test_env_admin_allowed_without_db_record(self) -> None:
        # Админ из .env получает доступ даже без записи в базе
        # и без похода в базу вообще.
        from handlers.admin.access import admin_guard

        event = helpers.make_admin_event("adm:addcat")
        event.from_user.id = 555
        handler = AsyncMock(return_value="passed")

        with (
            patch("handlers.admin.access.ConfigBot.ADMIN_IDS", (555,)),
            patch(
                "handlers.admin.access.get_user_by_telegram_id",
                new_callable=AsyncMock,
                return_value=REGULAR_USER,
            ) as lookup,
        ):
            result = await admin_guard(handler, event, {})

        self.assertEqual(result, "passed")
        lookup.assert_not_awaited()

    async def test_setup_attaches_guard_to_router(self) -> None:
        # Сборка в handlers/admin/__init__.py обязана защищать роутер.
        from aiogram import Router

        from handlers.admin.access import admin_guard, setup_admin_access

        checked = Router(name="test")
        setup_admin_access(checked)
        # outer_middleware — MiddlewareManager, он реализует Sequence.
        self.assertIn(admin_guard, checked.message.outer_middleware)
        self.assertIn(admin_guard, checked.callback_query.outer_middleware)

    async def test_command_shows_menu_for_admin(self) -> None:
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=777, username="boss", first_name="Ольга"),
            answer=AsyncMock(),
        )
        state = AsyncMock()

        with patch(
            "handlers.admin.router.admin_main_menu",
            return_value="menu",
        ):
            await admin_menu_command(message, state)

        state.clear.assert_awaited_once()
        message.answer.assert_awaited_once()
        self.assertIn("Панель администратора", message.answer.await_args.args[0])
        # В приветствии есть инструкция по возможностям панели.
        self.assertIn("Добавить товар", message.answer.await_args.args[0])
        self.assertIn("Подкатегории", message.answer.await_args.args[0])


if __name__ == "__main__":
    unittest.main()
