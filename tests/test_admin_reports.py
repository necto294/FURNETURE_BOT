"""Тесты статистики и экспорта заявок (кнопки в разделе «Заявки»).

Снимок статусов и полная CSV-выгрузка: словарь меток без эмодзи,
телефон в E.164, пустая база даёт сообщение вместо файла.
"""
import csv
import io
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from database import crud, engine
from database.engine import Base
from handlers.admin.orders import (
    build_orders_csv,
    orders_export_handler,
    orders_stats_handler,
)
from keyboard.admin_keyboards import orders_list_menu, orders_stats_menu


def make_state(data: dict | None = None) -> AsyncMock:
    state = AsyncMock()
    state.get_data = AsyncMock(return_value=data or {})
    return state


class _AnyMessageMeta(type):
    # Заставляем isinstance(x, _AnyMessage) всегда возвращать True.
    def __instancecheck__(cls, instance) -> bool:
        return True


class _AnyMessage(metaclass=_AnyMessageMeta):
    """Заменяет Message в isinstance-проверках обработчиков."""


def patch_orders_message():
    # Хендлеры импортируют Message в свой модуль — патчим там.
    return patch("handlers.admin.orders.Message", _AnyMessage)


def parse_csv(rows_text: str) -> list[list[str]]:
    """Разобрать CSV без стартового BOM."""
    return list(csv.reader(io.StringIO(rows_text.lstrip("﻿")), delimiter=";"))


def _order(
    order_id: int,
    name: str = "Диван",
    phone: str = "+79001234567",
    status: str = "new",
    customer_name: str = "Иван",
    price: int | None = 24990,
) -> SimpleNamespace:
    """Отсоединённая заявка, как её отдаёт crud.get_all_orders_full."""
    furniture = (
        SimpleNamespace(name=name, price=price)
        if name is not None
        else None
    )
    return SimpleNamespace(
        id=order_id,
        created_at=datetime(2026, 8, 23, 14, 5, tzinfo=timezone.utc),
        customer_name=customer_name,
        customer_phone=phone,
        status=status,
        user=SimpleNamespace(username="buyer"),
        furniture=furniture,
    )


class BuildOrdersCsvTests(unittest.TestCase):
    def test_full_dump_row_content(self) -> None:
        rows_text = build_orders_csv([_order(7)])
        # BOM в начале файла для распознавания UTF-8 в Excel.
        self.assertTrue(rows_text.startswith("﻿"))
        rows = parse_csv(rows_text)
        self.assertEqual(rows[0], ["№", "Дата", "Товар", "Цена", "Имя", "Телефон", "Статус"])
        self.assertEqual(rows[1][0], "7")
        self.assertEqual(rows[1][1], "23.08.2026 14:05")
        self.assertEqual(rows[1][2], "Диван")
        self.assertEqual(rows[1][3], "24990")
        self.assertEqual(rows[1][4], "Иван")
        # Телефон пишется как хранится — в международном формате.
        self.assertEqual(rows[1][5], "+79001234567")
        # Метка статуса без эмодзи, из словаря бота.
        self.assertEqual(rows[1][6], "Новая")

    def test_labels_without_emoji_and_crlf(self) -> None:
        orders = [
            _order(1, status="processing"),
            _order(2, status="completed"),
            _order(3, status="cancelled"),
        ]
        rows_text = build_orders_csv(orders)
        self.assertIn("В работе", rows_text)
        self.assertIn("Выполнена", rows_text)
        self.assertIn("Отменена", rows_text)
        for emoji in ("🆕", "🔧", "✅", "🚫"):
            self.assertNotIn(emoji, rows_text)
        # RFC 4180: перевод строки CRLF.
        self.assertIn("\r\n", rows_text)

    def test_missing_fields_stay_empty_cells(self) -> None:
        rows_text = build_orders_csv(
            [_order(9, name=None, phone="", customer_name="", price=None)]
        )
        row = parse_csv(rows_text)[1]
        self.assertEqual(row[2], "")  # товар удалён
        self.assertEqual(row[3], "")  # цена не указана
        self.assertEqual(row[4], "")
        self.assertEqual(row[5], "")

    def test_semicolon_in_name_is_quoted(self) -> None:
        rows_text = build_orders_csv([_order(5, customer_name="Иван; Петров")])
        row = parse_csv(rows_text)[1]
        self.assertEqual(row[4], "Иван; Петров")


class OrdersListMenuButtonsTests(unittest.TestCase):
    def test_header_has_stats_and_export_buttons(self) -> None:
        markup = orders_list_menu([], 0, 1)
        callbacks = [
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        ]
        self.assertIn("adm:ostats", callbacks)
        self.assertIn("adm:oexport", callbacks)

    def test_stats_screen_buttons(self) -> None:
        markup = orders_stats_menu()
        texts = [
            button.text for row in markup.inline_keyboard for button in row
        ]
        self.assertIn("⬇️ Экспорт CSV", texts)
        back = [
            button
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data == "adm:orders"
        ]
        self.assertTrue(back)


def make_callback(data: str) -> SimpleNamespace:
    return SimpleNamespace(
        message=SimpleNamespace(
            edit_text=AsyncMock(),
            answer_document=AsyncMock(),
        ),
        data=data,
        from_user=SimpleNamespace(id=777),
        answer=AsyncMock(),
    )


class OrdersStatsHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_renders_counts_and_total(self) -> None:
        callback = make_callback("adm:ostats")

        with (
            patch_orders_message(),
            patch(
                "handlers.admin.orders.get_order_status_counts",
                new_callable=AsyncMock,
                return_value={"new": 12, "completed": 3},
            ),
        ):
            await orders_stats_handler(callback)

        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("🆕 Новая — <b>12</b>", text)
        self.assertIn("— <b>0</b>", text)
        self.assertIn("Всего: <b>15</b>", text)
        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        callbacks = [
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        ]
        self.assertIn("adm:oexport", callbacks)
        self.assertIn("adm:orders", callbacks)
        callback.answer.assert_awaited_once()

    async def test_missing_statuses_shown_as_zero(self) -> None:
        callback = make_callback("adm:ostats")

        with (
            patch_orders_message(),
            patch(
                "handlers.admin.orders.get_order_status_counts",
                new_callable=AsyncMock,
                return_value={},
            ),
        ):
            await orders_stats_handler(callback)

        text = callback.message.edit_text.await_args.args[0]
        for label in ("🆕 Новая", "🔧 В работе", "✅ Выполнена", "🚫 Отменена"):
            self.assertIn(f"{label} — <b>0</b>", text)


class OrdersExportHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_export_sends_document_with_bom(self) -> None:
        callback = make_callback("adm:oexport")

        with (
            patch_orders_message(),
            patch(
                "handlers.admin.orders.get_all_orders_full",
                new_callable=AsyncMock,
                return_value=[_order(1), _order(2, status="completed")],
            ),
        ):
            await orders_export_handler(callback)

        callback.message.answer_document.assert_awaited_once()
        kwargs = callback.message.answer_document.await_args.kwargs
        document = callback.message.answer_document.await_args.args[0]
        self.assertTrue(document.filename.startswith("orders_"))
        self.assertTrue(document.filename.endswith(".csv"))
        content = document.data.decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        self.assertIn("+79001234567", content)
        caption = kwargs["caption"]
        self.assertIn("2", caption)
        callback.answer.assert_awaited_once()

    async def test_export_without_orders_sends_nothing(self) -> None:
        callback = make_callback("adm:oexport")

        with (
            patch_orders_message(),
            patch(
                "handlers.admin.orders.get_all_orders_full",
                new_callable=AsyncMock,
                return_value=[],
            ),
        ):
            await orders_export_handler(callback)

        callback.message.answer_document.assert_not_awaited()
        callback.answer.assert_awaited_once()
        self.assertTrue(callback.answer.await_args.kwargs.get("show_alert"))


class OrdersReportsCrudTests(unittest.IsolatedAsyncioTestCase):
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

    async def _make_orders(self) -> None:
        user = await crud.upsert_user(telegram_id=3001, first_name="Иван")
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            price=12990,
        )
        await crud.create_order(
            user_id=user.id,
            furniture_id=product.id,
            customer_name="Иван Петров",
            customer_phone="+70000000001",
        )
        second = await crud.create_order(
            user_id=user.id,
            furniture_id=product.id,
            customer_name="Пётр",
            customer_phone="+70000000002",
        )
        await crud.update_order_status(second.id, "completed")

    async def test_status_counts_snapshot(self) -> None:
        await self._make_orders()

        counts = await crud.get_order_status_counts()

        self.assertEqual(counts, {"new": 1, "completed": 1})

    async def test_all_orders_full_loads_relations(self) -> None:
        await self._make_orders()

        orders = await crud.get_all_orders_full()

        self.assertEqual(len(orders), 2)
        self.assertEqual([o.id for o in orders], [2, 1])  # свежие сверху
        # Связи загружены до отсоединения объекта от сессии.
        self.assertEqual(orders[0].furniture.price, 12990)
        self.assertEqual(orders[0].user.telegram_id, 3001)

    async def test_export_of_real_orders_is_valid_csv(self) -> None:
        await self._make_orders()

        orders = await crud.get_all_orders_full()
        rows_text = build_orders_csv(orders)
        rows = parse_csv(rows_text)

        self.assertEqual(len(rows), 3)  # шапка + две заявки
        phones = {rows[1][5], rows[2][5]}
        self.assertEqual(phones, {"+70000000001", "+70000000002"})
        statuses = {rows[1][6], rows[2][6]}
        self.assertEqual(statuses, {"Новая", "Выполнена"})


if __name__ == "__main__":
    unittest.main()
