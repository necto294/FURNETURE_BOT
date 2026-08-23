"""CRUD-тесты и хендлеры раздела заявок админ-панели.

Сценарные тесты потоков живут в test_admin_flows.py, авторизация —
в test_admin_access.py.
"""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

os.environ.setdefault("BOT_TOKEN", "test-token")

import helpers
from sqlalchemy import func, select

from database import crud
from database.models import FurniturePhoto


class AdminCrudTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def test_create_and_find_category(self) -> None:
        created = await crud.create_category("Шкафы", description="Корпусная мебель")
        found = await crud.get_category_by_name("Шкафы")
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(found.id, created.id)
        self.assertIsNone(await crud.get_category_by_name("Кровати"))

    async def test_delete_category_removes_products_and_photos(self) -> None:
        category = await crud.create_category("Спальная мебель")
        await crud.create_furniture_with_photos(
            name="Кровать",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            country="Россия",
            photos=[("file-1", "photos/file_1.jpg")],
        )

        self.assertTrue(await crud.delete_category(category.id))

        products = await crud.get_furniture_list(str(category.name))
        self.assertEqual(products, [])
        async with self.session_factory() as session:
            remaining = await session.scalar(
                select(func.count()).select_from(FurniturePhoto)
            )
        self.assertEqual(remaining, 0)

    async def test_subcategory_clear_keeps_products(self) -> None:
        category = await crud.create_category("Кухонная мебель")
        for _ in range(2):
            await crud.create_furniture_with_photos(
                name="Гарнитур",
                description=None,
                category_name=str(category.name),
                category_id=category.id,
                subcategory="Прямая",
            )

        items = await crud.get_subcategories_with_counts(str(category.name))
        self.assertEqual(items, [("Прямая", 2)])

        updated = await crud.clear_subcategory(str(category.name), "Прямая")
        self.assertEqual(updated, 2)
        products = await crud.get_furniture_list(str(category.name))
        self.assertEqual(len(products), 2)
        for product in products:
            self.assertIsNone(product.subcategory)

    async def test_delete_furniture_with_photos(self) -> None:
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-9", "photos/file_9.jpg")],
        )

        self.assertTrue(await crud.delete_furniture(product.id))
        self.assertIsNone(await crud.get_furniture_by_id(product.id))
        async with self.session_factory() as session:
            remaining = await session.scalar(
                select(func.count()).select_from(FurniturePhoto)
            )
        self.assertEqual(remaining, 0)

    async def test_created_product_photos_available_after_session(self) -> None:
        # Регрессия: после commit сессия закрывается, и ленивая загрузка
        # photos на отсоединённом объекте падала с DetachedInstanceError.
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
            photos=[("file-1", "photos/file_1.jpg"), ("file-2", "photos/file_2.jpg")],
        )

        self.assertEqual(len(product.photos), 2)
        self.assertEqual([photo.file_id for photo in product.photos], ["file-1", "file-2"])


class OrderNotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_confirm_sends_order_to_admins(self) -> None:
        os.environ.setdefault("BOT_TOKEN", "test-token")
        from handlers.backend.order import order_confirm_handler

        bot = SimpleNamespace(send_message=AsyncMock())
        callback = SimpleNamespace(
            from_user=SimpleNamespace(
                id=777, username="buyer", first_name="Иван", last_name="Петров"
            ),
            message=SimpleNamespace(edit_text=AsyncMock(), bot=bot),
            answer=AsyncMock(),
        )
        state = helpers.make_state(
            {
                "product_id": 42,
                "product_name": "<Диван>",
                "name": "Иван",
                "phone": "+70000000000",
            }
        )

        with (
            patch("handlers.backend.order.Message", helpers._AnyMessage),
            patch(
                "handlers.backend.order.upsert_user", new_callable=AsyncMock
            ) as upsert,
            patch(
                "handlers.backend.order.create_order", new_callable=AsyncMock
            ) as create_order,
            patch(
                "handlers.backend.order.get_categories", new_callable=AsyncMock
            ),
            patch("handlers.backend.order.main_menu", return_value="menu"),
            patch(
                "handlers.backend.order.get_admin_ids", new_callable=AsyncMock
            ) as admins,
        ):
            upsert.return_value = SimpleNamespace(id="user-1")
            create_order.return_value = SimpleNamespace(id=7)
            admins.return_value = [101, 202]
            with patch("handlers.backend.order.ConfigBot.ADMIN_IDS", (999,)):
                await order_confirm_handler(callback, state)

        # Получают и админ из .env, и админы из базы, без дубликатов.
        self.assertEqual(bot.send_message.await_count, 3)
        notified = [call.args[0] for call in bot.send_message.await_args_list]
        self.assertEqual(notified, [999, 101, 202])
        notification = bot.send_message.await_args_list[0].args[1]
        self.assertIn("№7", notification)
        self.assertIn("+70000000000", notification)
        self.assertIn("@buyer", notification)
        # Пользовательский ввод экранируется в уведомлении.
        self.assertNotIn("<Диван>", notification)
        self.assertIn("&lt;Диван&gt;", notification)


class AdminOrdersTests(helpers.TempDbMixin, unittest.IsolatedAsyncioTestCase):
    async def _make_order(self) -> tuple[object, object]:
        user = await crud.upsert_user(telegram_id=3001, first_name="Иван")
        category = await crud.create_category("Матрасы")
        product = await crud.create_furniture_with_photos(
            name="Матрас Ортопедик",
            description=None,
            category_name=str(category.name),
            category_id=category.id,
        )
        order = await crud.create_order(
            user_id=user.id,
            furniture_id=product.id,
            customer_name="Иван Петров",
            customer_phone="+70000000000",
        )
        return order, product

    async def test_orders_page_loads_relations(self) -> None:
        await self._make_order()

        orders, total = await crud.get_orders_page()

        self.assertEqual(total, 1)
        self.assertEqual(orders[0].customer_name, "Иван Петров")
        self.assertEqual(orders[0].customer_phone, "+70000000000")
        self.assertEqual(orders[0].furniture.name, "Матрас Ортопедик")
        self.assertEqual(orders[0].user.telegram_id, 3001)
        # Свежие заявки идут первыми.
        self.assertEqual(orders[0].status, "new")

    async def test_status_update_via_crud(self) -> None:
        order, _product = await self._make_order()

        updated = await crud.update_order_status(order.id, "processing")

        assert updated is not None
        self.assertEqual(updated.status, "processing")


class OrdersSectionHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_status_change_renders_updated_card(self) -> None:
        from handlers.admin.orders import order_status_handler

        callback = helpers.make_admin_event("adm:ost:5:processing:0")
        card = SimpleNamespace(
            id=5,
            status="processing",
            customer_name="Иван",
            customer_phone="+7000",
            created_at=None,
            user=SimpleNamespace(username="buyer"),
            furniture=SimpleNamespace(name="Диван", price=None),
        )

        with (
            helpers.patch_admin_message(),
            # orders.py импортирует Message отдельно — патчим и его.
            patch("handlers.admin.orders.Message", helpers._AnyMessage),
            patch(
                "handlers.admin.orders.update_order_status",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(status="processing"),
            ),
            patch(
                "handlers.admin.orders.get_order_by_id_full",
                new_callable=AsyncMock,
                return_value=card,
            ),
        ):
            await order_status_handler(callback)

        # Первый ответ — уведомление об успехе; второй лишь закрывает спиннер.
        first_answer = callback.answer.await_args_list[0]
        self.assertEqual(first_answer.args, ("Статус обновлён",))
        self.assertEqual(first_answer.kwargs, {"show_alert": False})
        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("№5", text)
        self.assertIn("+7000", text)


if __name__ == "__main__":
    unittest.main()
